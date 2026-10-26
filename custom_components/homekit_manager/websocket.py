"""Read-only WebSocket API for the future frontend."""
from __future__ import annotations
import probatio
from homeassistant.components import websocket_api
from .const import (
    BRIDGES_COMMAND, INVENTORY_COMMAND, PREVIEW_COMMAND, SAVE_DRAFT_COMMAND,
    VALIDATE_DRAFT_COMMAND, YAML_STATUS_COMMAND, PREPARE_OPTIONS_DIFF_COMMAND,
    RECONCILE_COMMAND, EXPORT_COMMAND,
)
from .homekit_writer import HomeKitWriteError
from .yaml_store import YamlStoreError, YamlValidationError, YamlVersionConflict

@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): INVENTORY_COMMAND, probatio.Optional("query"): str})
@websocket_api.async_response
async def websocket_inventory(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    query = (msg.get("query") or "").casefold()
    entities = coordinator.inventory
    if query:
        entities = [e for e in entities if query in (e.get("entity_id", "") + " " + (e.get("name") or "")).casefold()]
    connection.send_result(msg["id"], {"overview": coordinator.overview(), "entities": entities})

@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): BRIDGES_COMMAND})
@websocket_api.async_response
async def websocket_bridges(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    connection.send_result(msg["id"], {"bridges": coordinator.bridges})


def _document(msg):
    return msg.get("document") or msg.get("draft")


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): YAML_STATUS_COMMAND})
@websocket_api.async_response
async def websocket_yaml_status(hass, connection, msg):
    connection.send_result(msg["id"], hass.data["homekit_manager"]["coordinator"].yaml_status())


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): VALIDATE_DRAFT_COMMAND, probatio.Required("document"): dict})
@websocket_api.async_response
async def websocket_validate_draft(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    try:
        connection.send_result(msg["id"], coordinator.validate_draft(_document(msg)))
    except (YamlValidationError, ValueError) as err:
        connection.send_error(msg["id"], "invalid_format", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): PREVIEW_COMMAND, probatio.Required("document"): dict})
@websocket_api.async_response
async def websocket_preview(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    try:
        connection.send_result(msg["id"], coordinator.preview(_document(msg)))
    except (YamlValidationError, ValueError) as err:
        connection.send_error(msg["id"], "invalid_format", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({
    probatio.Required("type"): SAVE_DRAFT_COMMAND,
    probatio.Required("document"): dict,
    probatio.Optional("expected_file_version"): str,
    probatio.Optional("expected_fingerprint"): str,
})
@websocket_api.async_response
async def websocket_save_draft(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    try:
        result = coordinator.save_draft(_document(msg), msg.get("expected_file_version"), msg.get("expected_fingerprint"))
    except YamlVersionConflict as err:
        connection.send_error(msg["id"], "conflict", str(err))
        return
    except (YamlValidationError, ValueError) as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    except YamlStoreError as err:
        connection.send_error(msg["id"], "storage_error", str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): PREPARE_OPTIONS_DIFF_COMMAND, probatio.Required("document"): dict})
@websocket_api.async_response
async def websocket_prepare_options_diff(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    try:
        connection.send_result(msg["id"], coordinator.prepare_options_diff(_document(msg)))
    except (YamlValidationError, HomeKitWriteError, ValueError) as err:
        connection.send_error(msg["id"], "write_blocked", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): RECONCILE_COMMAND, probatio.Required("document"): dict, probatio.Optional("baseline_fingerprint"): str})
@websocket_api.async_response
async def websocket_reconcile(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    try:
        connection.send_result(msg["id"], coordinator.reconcile(_document(msg), msg.get("baseline_fingerprint")))
    except (YamlValidationError, ValueError) as err:
        connection.send_error(msg["id"], "invalid_format", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): EXPORT_COMMAND, probatio.Required("document"): dict, probatio.Optional("format"): str})
@websocket_api.async_response
async def websocket_export(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    try:
        connection.send_result(msg["id"], coordinator.export(_document(msg), msg.get("format", "yaml")))
    except (YamlValidationError, ValueError) as err:
        connection.send_error(msg["id"], "invalid_format", str(err))

def async_register_websocket_commands(hass, coordinator) -> None:
    """Register read-only commands; HA WebSocket auth is required by default."""
    websocket_api.async_register_command(hass, websocket_inventory)
    websocket_api.async_register_command(hass, websocket_bridges)
    for handler in (websocket_yaml_status, websocket_validate_draft, websocket_preview, websocket_save_draft, websocket_prepare_options_diff, websocket_reconcile, websocket_export):
        websocket_api.async_register_command(hass, handler)

