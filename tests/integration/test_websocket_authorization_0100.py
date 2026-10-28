"""Exercise the admin gate of every registered manager WebSocket command."""

from homeassistant.auth.const import GROUP_ID_USER

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
    }
    document_routes = {
        "homekit_manager/validate_draft", "homekit_manager/preview",
        "homekit_manager/save_draft", "homekit_manager/apply_options_diff",
        "homekit_manager/prepare_options_diff", "homekit_manager/reconcile",
        "homekit_manager/export",
    }
    for command in document_routes:
        args[command] = {"document": document}

    routes = {handler._ws_command for handler in REGISTERED_HANDLERS}
    assert len(routes) == len(REGISTERED_HANDLERS) == 32
    for route in sorted(routes):
        await client.send_json_auto_id({"type": route, **args.get(route, {})})
        response = await client.receive_json()
        assert response["type"] == "result" and response["success"] is False, (route, response)
        assert response["error"]["code"] == "unauthorized", (route, response)
