"""Admin WebSocket through manager coordinator to isolated Core writer."""
from homeassistant import config_entries

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
    assert native.options["filter"]["include_entities"] == ["light.before"]
    manager.operation_service = HomeKitOperationService(hass, isolated_write_authority=True)
    await client.send_json_auto_id({"type": "homekit_manager/operation_plan", "entry_id": native.entry_id,
                                    "document": document, "expected_fingerprint": manager.fingerprint})
    prepared = await client.receive_json()
    assert prepared["success"], prepared
    plan = prepared["result"]
    assert plan["apply_enabled"] is True
    await client.send_json_auto_id({"type": "homekit_manager/operation_apply", "operation_id": plan["operation_id"],
                                    "entry_id": native.entry_id, "source_revision": plan["source_revision"],
                                    "expected_fingerprint": manager.fingerprint,
                                    "confirmed_operation_id": plan["operation_id"]})
    response = await client.receive_json()
    assert response["success"], response
    assert response["result"]["state"] == "verified"
    assert native.options["filter"]["include_entities"] == ["light.after", "light.before"]
