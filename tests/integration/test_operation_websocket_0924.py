"""Admin WebSocket through manager coordinator to isolated Core writer."""
from homeassistant import config_entries
from homeassistant.config import async_hass_config_yaml
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.homekit_manager.operations import HomeKitOperationService


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
    assert response["result"]["state"] == "verified"
    assert native.options["filter"]["include_entities"] == ["light.after", "light.before"]


async def test_admin_operation_websocket_isolated_yaml_apply_and_verify(hass, tmp_path, enable_custom_integrations, hass_ws_client, monkeypatch):
    async def no_network_start(_self):
        return None
    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    (tmp_path / "configuration.yaml").write_text("homekit: !include bridges.yaml\n")
    source = tmp_path / "bridges.yaml"
    source.write_text("- name: WebSocket YAML Bridge\n  port: 21087\n  filter:\n    include_entities:\n    - light.before\n")
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
    await client.send_json_auto_id({"type": "homekit_manager/operation_plan", "entry_id": imported.entry_id,
                                    "document": document, "expected_fingerprint": manager.fingerprint})
    preview = await client.receive_json()
    assert preview["success"], preview
    plan = preview["result"]
    assert plan["source"] == config_entries.SOURCE_IMPORT
    assert plan["apply_enabled"] is True
    before = source.read_bytes()
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
        "# untouched\n"
        "homekit:\n"
        "  - name: Direct WS Bridge\n"
        "    port: 21090\n"
        "    filter:\n"
        "      include_entities:\n"
        "        - light.before\n"
        "logger:\n"
        "  default: warning\n"
    ).encode()
    source.write_bytes(before)
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
