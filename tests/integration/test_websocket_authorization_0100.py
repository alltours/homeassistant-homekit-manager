"""Exercise the admin gate of every registered manager WebSocket command."""

import json

from homeassistant.auth.const import GROUP_ID_USER
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homekit_manager.websocket import REGISTERED_HANDLERS


async def test_every_manager_websocket_route_rejects_authenticated_non_admin(
    hass, enable_custom_integrations, hass_ws_client,
):
    flow = await hass.config_entries.flow.async_init("homekit_manager", context={"source": "user"})
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    user = await hass.auth.async_create_user("limited-test-user", group_ids=[GROUP_ID_USER])
    refresh = await hass.auth.async_create_refresh_token(user, "http://localhost/")
    token = hass.auth.async_create_access_token(refresh)
    client = await hass_ws_client(access_token=token)

    document = {"schema_version": 1, "bridges": {}}
    args = {
        "homekit_manager/select_bridge": {"entry_id": "none"},
        "homekit_manager/device_preview": {"entity_id": "light.test"},
        "homekit_manager/rules_preview": {"rules": []},
        "homekit_manager/history_restore": {"index": 0},
        "homekit_manager/set_mode": {"mode": "homekit_bridge"},
        "homekit_manager/migration_start": {"target": "homekit_bridge"},
        "homekit_manager/operation_plan": {
            "document": document, "entry_id": "none", "expected_fingerprint": "none",
        },
        "homekit_manager/operation_apply": {
            "operation_id": "none", "entry_id": "none", "source_revision": "none",
            "expected_fingerprint": "none", "confirmed_operation_id": "none",
        },
        "homekit_manager/operation_status": {"operation_id": "none"},
        "homekit_manager/operation_reconcile": {"operation_id": "none"},
        "homekit_manager/test_write_mode_enable": {
            "entry_id": "none", "expected_fingerprint": "none", "confirmed_entry_id": "none",
        },
    }
    args["homekit_manager/bulk_preview"] = {"entry_id": "none", "fingerprint": "none", "kind": "device", "key": "device:none"}
    document_routes = {
        "homekit_manager/validate_draft", "homekit_manager/preview",
        "homekit_manager/save_draft", "homekit_manager/apply_options_diff",
        "homekit_manager/prepare_options_diff", "homekit_manager/reconcile",
        "homekit_manager/export",
    }
    for command in document_routes:
        args[command] = {"document": document}

    routes = {handler._ws_command for handler in REGISTERED_HANDLERS}
    assert len(routes) == len(REGISTERED_HANDLERS) == 36
    for route in sorted(routes):
        await client.send_json_auto_id({"type": route, **args.get(route, {})})
        response = await client.receive_json()
        assert response["type"] == "result" and response["success"] is False, (route, response)
        assert response["error"]["code"] == "unauthorized", (route, response)


async def test_bulk_preview_uses_server_scope_and_rejects_stale_or_wrong_bridge(
    hass, enable_custom_integrations, hass_ws_client,
):
    MockConfigEntry(domain="homekit", entry_id="bulk-bridge", source="user",
                    data={"name": "Bulk Bridge", "mode": "bridge"},
                    options={"filter": {}}).add_to_hass(hass)
    flow = await hass.config_entries.flow.async_init("homekit_manager", context={"source": "user"})
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    coordinator = hass.data["homekit_manager"]["coordinator"]
    coordinator.inventory = [
        {"entity_id": "light.first", "device_id": "device-one", "device_registry_status": "main", "registry_entry_present": True,
         "state_present": True, "compatibility": {"status": "supported"},
         "homekit": {"configured_by_filter": False}},
        {"entity_id": "sensor.diagnostic", "device_id": "device-one", "device_registry_status": "main", "registry_entry_present": True,
         "state_present": True, "entity_category": "diagnostic", "compatibility": {"status": "supported"},
         "homekit": {"configured_by_filter": False}},
    ]
    client = await hass_ws_client()
    payload = {"type": "homekit_manager/bulk_preview", "entry_id": "bulk-bridge",
               "fingerprint": coordinator.fingerprint, "kind": "device", "key": "device:device-one"}
    await client.send_json_auto_id(payload)
    result = await client.receive_json()
    assert result["success"] and result["result"]["eligible_entity_ids"] == ["light.first"]
    assert result["result"]["skipped"] == {"diagnostic": 1}
    await client.send_json_auto_id(payload | {"fingerprint": "stale"})
    assert (await client.receive_json())["error"]["code"] == "conflict"
    await client.send_json_auto_id(payload | {"entry_id": "another-bridge"})
    assert (await client.receive_json())["error"]["code"] == "conflict"


async def test_inventory_export_is_read_only_and_value_free(hass, enable_custom_integrations, hass_ws_client):
    native = MockConfigEntry(
        domain="homekit", entry_id="export-bridge", source="user",
        data={"name": "Export Bridge", "mode": "bridge"}, options={"filter": {}},
    )
    native.add_to_hass(hass)
    hass.states.async_set("light.export", "on", {"friendly_name": "Export light", "secret": "must not leave HA"})
    flow = await hass.config_entries.flow.async_init("homekit_manager", context={"source": "user"})
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    before = dict(native.options)
    client = await hass_ws_client()

    await client.send_json_auto_id({"type": "homekit_manager/inventory_export", "format": "json"})
    response = await client.receive_json()
    assert response["success"], response
    result = response["result"]
    document = json.loads(result["content"])
    assert document["schema_version"] == 1
    assert any(item["entity_id"] == "light.export" for item in document["entities"])
    assert "secret" not in result["content"]
    assert "attributes" not in result["content"]
    assert dict(native.options) == before

    await client.send_json_auto_id({"type": "homekit_manager/inventory_export", "format": "csv"})
    csv_response = await client.receive_json()
    assert csv_response["success"] and csv_response["result"]["content"].startswith("entity_id,")
    await client.send_json_auto_id({"type": "homekit_manager/inventory_export", "format": "yaml"})
    assert (await client.receive_json())["error"]["code"] == "invalid_format"
    assert dict(native.options) == before
