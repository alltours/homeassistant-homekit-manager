"""Release blockers and safety boundaries exercised in real isolated HA."""
import asyncio
from copy import deepcopy
from unittest.mock import Mock

import pytest
from homeassistant import config_entries
from homeassistant.components import frontend, websocket_api
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser
from custom_components.homekit_manager.compatibility import classify_entity
from custom_components.homekit_manager.homekit_writer import HomeKitWriteDisabled, HomeKitWriter
from custom_components.homekit_manager.yaml_store import validate_document, YamlValidationError


async def setup_manager(hass):
    flow = await hass.config_entries.flow.async_init("homekit_manager", context={"source": "user"})
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    return hass.data["homekit_manager"]["coordinator"]


@pytest.mark.parametrize("status", [[], {}, None, 1, True, "included"])
def test_malformed_status_is_a_controlled_validation_error(status):
    with pytest.raises(YamlValidationError):
        validate_document({"schema_version": 1, "bridges": {"b": {"policy": "explicit_overrides", "entities": {"light.one": status}}}})


@pytest.mark.parametrize("domain,device_class,features", [("camera", None, 0), ("lock", None, 0), ("media_player", "tv", 0), ("remote", None, 4)])
def test_accessory_mode_matches_native_core_eligibility(domain, device_class, features):
    from homeassistant.core import State
    from homeassistant.components.homekit.util import state_needs_accessory_mode
    from homeassistant.components.remote import RemoteEntityFeature
    if domain == "remote":
        features = int(RemoteEntityFeature.ACTIVITY)
    attrs = {"device_class": device_class, "supported_features": features}
    assert state_needs_accessory_mode(State(f"{domain}.test", "on", attrs))
    assert classify_entity({"domain": domain, "attributes": attrs}, "bridge").status == "unsupported"


async def test_bridge_and_accessory_entries_are_separate(hass, enable_custom_integrations):
    for entry_id, mode in (("bridge-one", "bridge"), ("accessory-one", "accessory")):
        MockConfigEntry(domain="homekit", entry_id=entry_id, data={"name": entry_id}, options={"homekit_mode": mode, "filter": {}}).add_to_hass(hass)
    manager = await setup_manager(hass)
    assert [item["entry_id"] for item in manager.bridges] == ["bridge-one"]
    assert [item["entry_id"] for item in manager.accessories] == ["accessory-one"]
    assert manager.overview()["bridges"] == 1
    assert manager.selected_bridge_id == "bridge-one"
    with pytest.raises(ValueError):
        await manager.async_select_bridge("accessory-one")


async def test_yaml_import_entry_is_not_counted_as_a_second_native_source(hass, tmp_path, enable_custom_integrations):
    (tmp_path / "configuration.yaml").write_text("homekit:\n  - name: Test YAML Bridge\n    port: 21066\n")
    MockConfigEntry(domain="homekit", entry_id="yaml-one", source="import",
                    data={"name": "Test YAML Bridge", "port": 21066, "mode": "bridge"},
                    options={"filter": {}}).add_to_hass(hass)
    manager = await setup_manager(hass)
    assert manager.configuration_sources["active_mode"] == "yaml"
    assert manager.configuration_sources["mixed"] is False
    assert manager.bridges[0]["source"] == "import"


async def test_failed_refresh_preserves_complete_snapshot(hass, enable_custom_integrations, monkeypatch):
    manager = await setup_manager(hass)
    before = (manager.inventory, manager.bridges, manager.devices, manager.areas, manager.fingerprint, manager.last_updated)
    def fail(*args, **kwargs):
        raise ValueError("injected invalid inventory")
    monkeypatch.setattr("custom_components.homekit_manager.coordinator.build_device_views", fail)
    await manager.async_refresh()
    after = (manager.inventory, manager.bridges, manager.devices, manager.areas, manager.fingerprint, manager.last_updated)
    assert all(left is right for left, right in zip(before, after))
    assert manager.overview()["snapshot_stale"] is True


async def test_identical_state_events_do_not_recompute_and_burst_is_coalesced(hass, enable_custom_integrations):
    manager = await setup_manager(hass)
    before = manager.refresh_count
    old = Mock(state="on", attributes={"x": 1})
    for _ in range(100):
        manager._event_received(Mock(event_type="state_changed", data={"old_state": old, "new_state": old}))
    assert manager.events_seen == 100
    assert manager.events_ignored == 100
    assert manager.refresh_count == before
    assert manager._refresh_task is None
    for index in range(25):
        manager._event_received(Mock(event_type="state_changed", data={"old_state": old,
                                   "new_state": Mock(state="on", attributes={"x": index + 2})}))
    await asyncio.sleep(1.35)
    assert manager.refresh_count == before + 1
    assert manager.events_seen == 125
    assert manager.refresh_cpu_ms is not None
    assert set(manager.refresh_phases_ms) == {"registry_inventory", "filter_compatibility", "grouping", "source_io", "diagnostics_fingerprint"}
    assert manager.overview()["refresh_requests"] >= manager.refresh_count


async def test_unload_reload_removes_and_restores_commands(hass, enable_custom_integrations):
    await setup_manager(hass)
    entry = hass.config_entries.async_entries("homekit_manager")[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not any(key.startswith("homekit_manager/") for key in hass.data[websocket_api.DOMAIN])
    assert not frontend.async_panel_exists(hass, "homekit_manager")
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert "homekit_manager/inventory" in hass.data[websocket_api.DOMAIN]
    assert frontend.async_panel_exists(hass, "homekit_manager")


async def test_unknown_activation_is_durable_and_never_retried(hass, enable_custom_integrations, monkeypatch):
    manager = await setup_manager(hass)
    await manager.async_record_activation_status("bridge-one", "operation-one", "activating", options_saved=True)
    entry = hass.config_entries.async_entries("homekit_manager")[0]
    await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    manager = hass.data["homekit_manager"]["coordinator"]
    status = manager.activation_status("bridge-one", "operation-one")
    assert status["state"] == "unknown"
    assert status["persistent"] is True
    assert status["automatic_retry"] is False
    writer = Mock()
    monkeypatch.setattr("custom_components.homekit_manager.coordinator.HomeKitWriter", writer)
    for request_id in ("operation-one", "operation-two"):
        with pytest.raises(HomeKitWriteDisabled):
            await manager.async_apply_options_diff({}, None, request_id)
    writer.assert_not_called()
    assert manager.activation_status("bridge-one")["state"] == "unknown"


async def test_apply_http_transport_is_locked_and_native_options_unchanged(hass, enable_custom_integrations, hass_ws_client):
    native = MockConfigEntry(domain="homekit", data={"name": "Protected Bridge"}, options={"filter": {"include_entities": ["light.one"]}})
    native.add_to_hass(hass)
    before = deepcopy(dict(native.options))
    manager = await setup_manager(hass)
    client = await hass_ws_client()
    for request_id in ("old", "new"):
        await client.send_json_auto_id({"type": "homekit_manager/apply_options_diff", "document": {"schema_version": 1, "bridges": {}}, "request_id": request_id})
        response = await client.receive_json()
        assert response["success"] is False
        assert response["error"]["code"] == "write_blocked"
    assert dict(native.options) == before
    assert manager.overview()["write_policy"]["enabled"] is False


async def test_all_api_commands_reject_non_administrators(hass, enable_custom_integrations, hass_ws_client):
    await setup_manager(hass)
    user = MockUser().add_to_hass(hass)
    refresh = await hass.auth.async_create_refresh_token(user, client_id="http://localhost")
    client = await hass_ws_client(access_token=hass.auth.async_create_access_token(refresh))
    from custom_components.homekit_manager.websocket import REGISTERED_HANDLERS
    document = {"schema_version": 1, "bridges": {}}
    arguments = {"select_bridge": {"entry_id": "b"}, "device_preview": {"entity_id": "light.one"}, "rules_preview": {"rules": []}, "history_restore": {"index": 0}, "set_mode": {"mode": "homekit_bridge"}, "migration_start": {"target": "homekit_bridge"}, "management_enable": {}, "management_disable": {}}
    for handler in REGISTERED_HANDLERS:
        command = handler._ws_command
        name = command.split("/")[1]
        args = arguments.get(name, {})
        if name in {"validate_draft", "preview", "save_draft", "prepare_options_diff", "apply_options_diff", "reconcile", "export"}:
            args = {"document": document}
        await client.send_json_auto_id({"type": command, **args})
        response = await client.receive_json()
        assert response["success"] is False, command
        assert response["error"]["code"] == "unauthorized", (command, response)


async def test_drafts_merge_across_bridges_and_history_restores_only_its_bridge(hass, enable_custom_integrations):
    for entry_id in ("one", "two"):
        MockConfigEntry(domain="homekit", entry_id=entry_id, data={"name": entry_id}, options={"filter": {}}).add_to_hass(hass)
    manager = await setup_manager(hass)
    for bridge_id in ("one", "two"):
        await manager.async_select_bridge(bridge_id)
        doc = {"schema_version": 1, "bridges": {bridge_id: {"policy": "explicit_overrides", "entities": {f"light.{bridge_id}": "exclude"}}}}
        saved = await manager.async_save_draft(doc, manager.yaml_snapshot.file_version, manager.fingerprint)
        assert saved["exists"]
    assert set(saved["document"]["bridges"]) == {"one", "two"}
    restored = manager.restore_history(1)
    assert restored["bridge_id"] == "two"
    assert set(restored["document"]["bridges"]) == {"two"}
    await manager.async_select_bridge("one")
    with pytest.raises(YamlValidationError):
        await manager.async_save_draft(doc, manager.yaml_snapshot.file_version, manager.fingerprint)


async def test_management_metadata_survives_reload_and_rejects_changed_context(hass, enable_custom_integrations, monkeypatch):
    manager = await setup_manager(hass)
    manager.bridges = [{"entry_id": "one", "title": "One", "source": "user", "mode": "bridge", "state": "loaded", "filter": {}}]
    manager.selected_bridge_id = "one"
    async def keep_test_bridge():
        pass
    monkeypatch.setattr(manager, "async_refresh", keep_test_bridge)
    with pytest.raises(ValueError, match="Bridge wurde geändert"):
        await manager.async_enable_management(True, "two")
    result = await manager.async_enable_management(True, "one")
    assert result["active"]
    manager.management_statuses = await manager.management_store.async_load()
    assert manager.management_status()["active"]
    await manager.async_record_activation_status("one", "old", "unknown")
    assert manager.management_status()["supported"] is False
    assert (await manager.async_disable_management(True, "one"))["state"] == "blocked"


async def test_partial_setup_failure_cleans_up_handlers_and_listeners(hass, enable_custom_integrations, monkeypatch):
    from custom_components.homekit_manager import async_setup
    async def fail_panel(_hass):
        raise RuntimeError("injected registration failure")
    monkeypatch.setattr("custom_components.homekit_manager.panel.async_register_panel", fail_panel)
    assert await async_setup(hass, {}) is False
    assert "homekit_manager" not in hass.data
    assert not any(key.startswith("homekit_manager/") for key in hass.data[websocket_api.DOMAIN])
    assert not frontend.async_panel_exists(hass, "homekit_manager")


async def test_frontend_snapshot_has_one_bridge_and_fingerprint(hass, enable_custom_integrations, hass_ws_client):
    MockConfigEntry(domain="homekit", entry_id="one", data={"name": "One"}, options={"filter": {}}).add_to_hass(hass)
    await setup_manager(hass)
    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "homekit_manager/inventory", "include_context": True, "refresh": True})
    response = await client.receive_json()
    assert response["success"]
    data = response["result"]
    assert len(data["context"]) == 11
    assert data["context"][0]["bridges"][0]["entry_id"] == data["overview"]["selected_bridge_id"]
    assert data["context"][5]["fingerprint"] == data["overview"]["fingerprint"]


@pytest.mark.parametrize("rules,manual", [([None], None), ([{"action": []}], None), ([{"action": "include", "priority": []}], None), ([{"action": "include", "match": []}], None), ([], {"light.one": []})])
def test_malformed_rules_are_controlled(rules, manual):
    from custom_components.homekit_manager.rules import evaluate_rules
    with pytest.raises(ValueError):
        evaluate_rules([], rules, manual)


def test_entity_prefix_rule_matches_actual_entity_id():
    from custom_components.homekit_manager.rules import evaluate_rules
    result = evaluate_rules([{"entity_id": "light.one"}], [{"action": "exclude", "match": {"entity_id_prefix": "light."}}])
    assert result["decisions"][0]["decision"] == "exclude"


async def test_history_failure_reports_saved_draft_truthfully(hass, enable_custom_integrations, monkeypatch):
    MockConfigEntry(domain="homekit", entry_id="one", data={"name": "One"}, options={"filter": {}}).add_to_hass(hass)
    manager = await setup_manager(hass)
    async def fail_history(_entries):
        raise OSError("isolated full disk simulation")
    monkeypatch.setattr(manager.history_store, "async_save", fail_history)
    result = await manager.async_save_draft({"schema_version": 1, "bridges": {"one": {"policy": "explicit_overrides", "entities": {}}}}, None, manager.fingerprint)
    assert result["valid"] and result["exists"] and result["history_error"]
    assert manager.yaml_store.load().document == result["document"]
    assert manager.history_entries == []


async def test_event_bursts_coalesce_without_losing_last_state(hass, enable_custom_integrations):
    manager = await setup_manager(hass)
    count = manager.refresh_count
    for number in range(100):
        hass.states.async_set("light.burst", str(number))
    await asyncio.sleep(1.4)
    assert 1 <= manager.refresh_count - count <= 2
    assert next(item for item in manager.inventory if item["entity_id"] == "light.burst")["state"] == "99"


async def test_native_yaml_include_cannot_be_overwritten_by_draft_save(hass, enable_custom_integrations):
    from custom_components.homekit_manager.yaml_store import YamlWriteError
    MockConfigEntry(domain="homekit", entry_id="one", data={"name": "One"}, options={"filter": {}}).add_to_hass(hass)
    manager = await setup_manager(hass)
    manager.configuration_sources["manager_include"] = True
    with pytest.raises(YamlWriteError, match="nicht überschrieben"):
        await manager.async_save_draft({"schema_version": 1, "bridges": {"one": {"policy": "explicit_overrides", "entities": {}}}}, None, manager.fingerprint)
    assert not manager.yaml_store.path.exists()


@pytest.mark.parametrize("timestamp", [None, "invalid", "2026-10-27T08:00:00", "2099-01-01T00:00:00+00:00"])
async def test_corrupt_migration_timestamps_recover_as_unknown(hass, timestamp):
    from custom_components.homekit_manager.migration_store import MigrationStore
    store = MigrationStore(hass)
    await store._store.async_save({"status": {"state": "completed", "updated_at": timestamp}})
    result = await store.async_load()
    assert result["state"] == "unknown" and result["stale"]
