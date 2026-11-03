"""Admin WebSocket through manager coordinator to isolated Core writer."""
from file_helpers import secure_private_source
from homeassistant import config_entries
from homeassistant.config import async_hass_config_yaml
from homeassistant.const import __version__
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.homekit_manager.operations import HomeKitOperationService
from custom_components.homekit_manager.selection_draft import empty_draft


async def test_admin_operation_websocket_isolated_apply_and_verify(hass, enable_custom_integrations, hass_ws_client, monkeypatch):
    async def no_network_start(_self):
        return None
    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    native = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="WebSocket Test Bridge",
        data={"name": "WebSocket Test Bridge", "port": 21085},
        options={"mode": "bridge", "filter": {"include_entities": ["light.before"]}},
        source=config_entries.SOURCE_USER, entry_id="websocket-isolated-native", unique_id=None,
        discovery_keys={}, subentries_data=None,
    )
    await hass.config_entries.async_add(native)
    await hass.async_block_till_done()
    hass.states.async_set("light.before", "on")
    assert er.async_get(hass).async_get_or_create("light", "test", "after", suggested_object_id="after").entity_id == "light.after"
    hass.states.async_set("light.after", "on")
    flow = await hass.config_entries.flow.async_init("homekit_manager", context={"source": "user"})
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    manager = hass.data["homekit_manager"]["coordinator"]
    assert manager.selected_bridge_id == native.entry_id
    client = await hass_ws_client()
    document = {"schema_version": 1, "bridges": {native.entry_id: {"policy": "explicit_overrides", "entities": {"light.after": "include"}}}}
    await client.send_json_auto_id({"type": "homekit_manager/operation_plan", "entry_id": native.entry_id,
                                    "document": document, "expected_fingerprint": manager.fingerprint})
    preview = await client.receive_json()
    assert preview["success"], preview
    plan = preview["result"]
    assert plan["apply_enabled"] is False
    await client.send_json_auto_id({"type": "homekit_manager/operation_apply", "operation_id": plan["operation_id"],
                                    "entry_id": native.entry_id, "source_revision": plan["source_revision"],
                                    "expected_fingerprint": manager.fingerprint,
                                    "confirmed_operation_id": plan["operation_id"]})
    assert (await client.receive_json())["success"] is False
    assert native.options["filter"]["include_entities"] == ["light.before"]
    manager.operation_service.test_write_mode.enable(hass, native.entry_id, native.entry_id)
    await client.send_json_auto_id({"type": "homekit_manager/operation_plan", "entry_id": native.entry_id,
                                    "document": document, "expected_fingerprint": manager.fingerprint})
    preview = await client.receive_json()
    assert preview["success"], preview
    plan = preview["result"]
    assert plan["apply_enabled"] is True
    assert plan["change_details"] == [{"entity_id": "light.after", "current": "excluded",
                                        "desired": "included", "action": "add", "risk": "low",
                                        "reason": "explicit_include", "blocked": False,
                                        "filter_impact": None}]
    assert native.options["filter"]["include_entities"] == ["light.before"]
    await client.send_json_auto_id({"type": "homekit_manager/operation_apply", "operation_id": plan["operation_id"],
                                    "entry_id": native.entry_id, "source_revision": plan["source_revision"],
                                    "expected_fingerprint": manager.fingerprint,
                                    "confirmed_operation_id": plan["operation_id"]})
    response = await client.receive_json()
    assert response["success"], response
    assert response["result"]["state"] == "verification_incomplete"
    assert native.options["filter"]["include_entities"] == ["light.after", "light.before"]


async def test_selection_draft_websocket_bridges_into_existing_native_operation_engine(
    hass, enable_custom_integrations, hass_ws_client, monkeypatch,
):
    async def no_network_start(_self):
        return None
    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    native = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="Selection Apply Bridge",
        data={"name": "Selection Apply Bridge", "port": 21089},
        options={"mode": "bridge", "filter": {"include_entities": ["light.before", "light.after"]}},
        source=config_entries.SOURCE_USER, entry_id="selection-apply-native", unique_id=None,
        discovery_keys={}, subentries_data=None,
    )
    await hass.config_entries.async_add(native)
    await hass.async_block_till_done()
    flow = await hass.config_entries.flow.async_init("homekit_manager", context={"source": "user"})
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    manager = hass.data["homekit_manager"]["coordinator"]
    manager.operation_service = HomeKitOperationService(hass, isolated_write_authority=True)
    row = {
        "entity_id": "light.before",
        "name": "Before",
        "identity": {"entity_id": "light.before", "unique_id": "uid-before", "device_id": "device-before"},
        "homekit": {"configured_by_filter": True},
        "compatibility": {"status": "supported"},
        "registry_entry_present": True,
        "state_present": True,
        "available": True,
    }
    retained = {
        **row,
        "entity_id": "light.after",
        "name": "After",
        "identity": {"entity_id": "light.after", "unique_id": "uid-after", "device_id": "device-after"},
    }
    snapshot = {
        "bridge_entry_id": native.entry_id,
        "bridge_title": native.title,
        "snapshot_revision": 4,
        "snapshot_fingerprint": "selection-snapshot",
        "snapshot_complete": True,
        "selection_conflict": False,
        "metadata_unresolved": False,
        "native_filter": {"include_entities": ["light.before", "light.after"]},
        "current_entity_ids": ["light.before", "light.after"],
        "runtime_entity_ids": ["light.before", "light.after"],
        "current_entities": [row, retained],
        "stale_manager_decisions": [],
        "stale_native_includes": [],
        "runtime_completeness": "complete",
        "ambiguous_runtime_count": 0,
    }
    manager._selection_snapshot = lambda: snapshot
    manager.inventory = [row, retained]
    manager.fingerprint = "selection-snapshot"
    draft = empty_draft(native.entry_id, 4, "selection-snapshot")
    draft["decisions"]["light.before"] = {
        "decision": "REMOVE", "decision_source": "user", "confirmation_status": "confirmed",
        "identity": row["identity"],
    }
    draft["decisions"]["light.after"] = {
        "decision": "KEEP", "decision_source": "user", "confirmation_status": "confirmed",
        "identity": retained["identity"],
    }
    client = await hass_ws_client()
    await client.send_json_auto_id({
        "type": "homekit_manager/selection_operation_plan",
        "entry_id": native.entry_id,
        "expected_fingerprint": "selection-snapshot",
        "draft": draft,
    })
    preview = await client.receive_json()
    assert preview["success"], preview
    plan = preview["result"]
    assert plan["changed_entities"] == ["light.before"]
    assert plan["apply_enabled"] is True
    assert native.options["filter"]["include_entities"] == ["light.before", "light.after"]
    await client.send_json_auto_id({
        "type": "homekit_manager/operation_apply",
        "operation_id": plan["operation_id"],
        "entry_id": native.entry_id,
        "source_revision": plan["source_revision"],
        "expected_fingerprint": "selection-snapshot",
        "confirmed_operation_id": plan["operation_id"],
    })
    result = await client.receive_json()
    assert result["success"], result
    assert result["result"]["state"] == "verification_incomplete"
    assert native.options["filter"]["include_entities"] == ["light.after"]


async def test_admin_operation_websocket_isolated_yaml_apply_and_verify(hass, tmp_path, enable_custom_integrations, hass_ws_client, monkeypatch):
    async def no_network_start(_self):
        return None
    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    (tmp_path / "configuration.yaml").write_text("homekit: !include bridges.yaml\n")
    secure_private_source(tmp_path / "configuration.yaml")
    source = tmp_path / "bridges.yaml"
    source.write_text("- name: WebSocket YAML Bridge\n  port: 21087\n  filter:\n    include_entities:\n    - light.before\n")
    secure_private_source(source)
    assert await async_setup_component(hass, "homekit", await async_hass_config_yaml(hass))
    await hass.async_block_till_done()
    imported = hass.config_entries.async_entries("homekit")[0]
    assert imported.source == config_entries.SOURCE_IMPORT
    hass.states.async_set("light.before", "on")
    assert er.async_get(hass).async_get_or_create("light", "test", "after", suggested_object_id="after").entity_id == "light.after"
    hass.states.async_set("light.after", "on")
    flow = await hass.config_entries.flow.async_init("homekit_manager", context={"source": "user"})
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    manager = hass.data["homekit_manager"]["coordinator"]
    assert manager.selected_bridge_id == imported.entry_id
    manager.operation_service = HomeKitOperationService(hass, isolated_write_authority=True)
    client = await hass_ws_client()
    document = {"schema_version": 1, "bridges": {imported.entry_id: {"policy": "explicit_overrides", "entities": {"light.after": "include"}}}}
    before = source.read_bytes()
    await client.send_json_auto_id({"type": "homekit_manager/operation_plan", "entry_id": imported.entry_id,
                                    "document": document, "expected_fingerprint": manager.fingerprint})
    preview = await client.receive_json()
    if __version__ != "2026.10.4":
        assert preview["success"] is False
        assert preview["error"]["message"] == "YAML-Apply ist für diese Core-Version nicht verifiziert"
        assert source.read_bytes() == before
        return
    assert preview["success"], preview
    plan = preview["result"]
    assert plan["source"] == config_entries.SOURCE_IMPORT
    assert plan["apply_enabled"] is True
    await client.send_json_auto_id({"type": "homekit_manager/operation_apply", "operation_id": plan["operation_id"],
                                    "entry_id": imported.entry_id, "source_revision": plan["source_revision"],
                                    "expected_fingerprint": manager.fingerprint,
                                    "confirmed_operation_id": plan["operation_id"]})
    response = await client.receive_json()
    assert response["success"], response
    assert response["result"]["state"] == "verified"
    assert source.read_bytes() != before
    assert (tmp_path / ".storage" / "homekit_manager_backups" / f"{plan['operation_id']}.yaml").read_bytes() == before
    updated = hass.config_entries.async_get_entry(imported.entry_id)
    assert updated.entry_id == imported.entry_id
    assert updated.options["filter"]["include_entities"] == ["light.after", "light.before"]


async def test_admin_websocket_direct_yaml_apply_preserves_other_config(hass, tmp_path, enable_custom_integrations, hass_ws_client, monkeypatch):
    async def no_network_start(_self):
        return None
    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    source = tmp_path / "configuration.yaml"
    before = (
        b"# untouched\n"
        b"homekit:\n"
        b"  - name: Direct WS Bridge\n"
        b"    port: 21090\n"
        b"    filter:\n"
        b"      include_entities:\n"
        b"        - light.before\n"
        b"logger:\n"
        b"  default: warning\n"
    )
    source.write_bytes(before)
    secure_private_source(source)
    assert await async_setup_component(hass, "homekit", await async_hass_config_yaml(hass))
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries("homekit")[0]
    assert entry.source == config_entries.SOURCE_IMPORT
    hass.states.async_set("light.before", "on")
    assert er.async_get(hass).async_get_or_create("light", "test", "after", suggested_object_id="after").entity_id == "light.after"
    hass.states.async_set("light.after", "on")
    flow = await hass.config_entries.flow.async_init("homekit_manager", context={"source": "user"})
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    manager = hass.data["homekit_manager"]["coordinator"]
    manager.operation_service = HomeKitOperationService(hass, isolated_write_authority=True)
    client = await hass_ws_client()
    document = {"schema_version": 1, "bridges": {entry.entry_id: {
        "policy": "explicit_overrides", "entities": {"light.after": "include"}}}}
    await client.send_json_auto_id({"type": "homekit_manager/operation_plan", "entry_id": entry.entry_id,
                                    "document": document, "expected_fingerprint": manager.fingerprint})
    preview = await client.receive_json()
    if __version__ != "2026.10.4":
        assert preview["success"] is False
        assert preview["error"]["message"] == "YAML-Apply ist für diese Core-Version nicht verifiziert"
        assert source.read_bytes() == before
        return
    assert preview["success"], preview
    plan = preview["result"]
    await client.send_json_auto_id({"type": "homekit_manager/operation_apply", "operation_id": plan["operation_id"],
                                    "entry_id": entry.entry_id, "source_revision": plan["source_revision"],
                                    "expected_fingerprint": manager.fingerprint,
                                    "confirmed_operation_id": plan["operation_id"]})
    result = await client.receive_json()
    assert result["success"] and result["result"]["state"] == "verified", result
    assert source.read_bytes().startswith(b"# untouched\n")
    assert source.read_bytes().endswith(b"logger:\n  default: warning\n")
    backup = tmp_path / ".storage" / "homekit_manager_backups" / f"{plan['operation_id']}.yaml"
    assert backup.read_bytes() == before
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.source == config_entries.SOURCE_IMPORT
    assert updated.options["filter"]["include_entities"] == ["light.after", "light.before"]
