"""Authenticated WebSocket API for read operations and controlled drafts.

All commands require an administrator connection. HomeKit writes are locked
in 0.9.19 before any native options or operation state can change.
"""
from __future__ import annotations
import probatio
from homeassistant.components import websocket_api
from .const import (
    BRIDGES_COMMAND, SELECT_BRIDGE_COMMAND, INVENTORY_COMMAND, PREVIEW_COMMAND, SAVE_DRAFT_COMMAND, APPLY_OPTIONS_DIFF_COMMAND,
    VALIDATE_DRAFT_COMMAND, YAML_STATUS_COMMAND, PREPARE_OPTIONS_DIFF_COMMAND,
    RECONCILE_COMMAND, EXPORT_COMMAND,
    MODE_STATUS_COMMAND, SET_MODE_COMMAND,
    DEVICES_COMMAND, AREAS_COMMAND, DIAGNOSTICS_COMMAND, DEVICE_PREVIEW_COMMAND, RULES_PREVIEW_COMMAND, HISTORY_COMMAND, HISTORY_RESTORE_COMMAND, PERFORMANCE_COMMAND,
    ACTIVATION_STATUS_COMMAND,
    MIGRATION_PLAN_COMMAND, MIGRATION_START_COMMAND, MIGRATION_STATUS_COMMAND,
    MANAGEMENT_STATUS_COMMAND, MANAGEMENT_ENABLE_COMMAND, MANAGEMENT_DISABLE_COMMAND,
)
from .homekit_writer import HomeKitWriteError
from .yaml_store import YamlStoreError, YamlValidationError, YamlVersionConflict
from .device_config import build_preview
from .rules import evaluate_rules
from .performance import summarize_inventory

@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): INVENTORY_COMMAND, probatio.Optional("query"): str, probatio.Optional("refresh", default=False): bool, probatio.Optional("include_context", default=False): bool})
@websocket_api.async_response
async def websocket_inventory(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    if msg.get("refresh"):
        await coordinator.async_refresh()
    query = (msg.get("query") or "").casefold()
    entities = coordinator.inventory
    if query:
        entities = [e for e in entities if query in (e.get("entity_id", "") + " " + (e.get("name") or "")).casefold()]
    result = {"overview": coordinator.overview(), "entities": entities}
    if msg.get("include_context"):
        # One event-loop turn, no awaits: every section has the same bridge context.
        result["context"] = [
            {"bridges": coordinator.bridges, "accessories": coordinator.accessories},
            {"devices": coordinator.devices}, {"areas": coordinator.areas},
            coordinator.diagnostics(), coordinator.history(),
            coordinator._yaml_status_payload(coordinator.yaml_snapshot),
            coordinator.mode_status(), coordinator.activation_status(),
            coordinator.migration_plan(), coordinator.migration_status_snapshot(),
            coordinator.management_status(),
        ]
    connection.send_result(msg["id"], result)

@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): BRIDGES_COMMAND})
@websocket_api.async_response
async def websocket_bridges(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    connection.send_result(msg["id"], {"bridges": coordinator.bridges, "accessories": coordinator.accessories, "unclassified": coordinator.other_homekit_entries})


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): SELECT_BRIDGE_COMMAND, probatio.Required("entry_id"): str})
@websocket_api.async_response
async def websocket_select_bridge(hass, connection, msg):
    """Switch the read-only bridge context without changing HomeKit."""
    coordinator = hass.data["homekit_manager"]["coordinator"]
    try:
        connection.send_result(msg["id"], await coordinator.async_select_bridge(msg["entry_id"]))
    except ValueError as err:
        connection.send_error(msg["id"], "unknown_bridge", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): DEVICES_COMMAND})
@websocket_api.async_response
async def websocket_devices(hass, connection, msg):
    """Return aggregated device views; this endpoint never writes registries."""
    coordinator = hass.data["homekit_manager"]["coordinator"]
    connection.send_result(msg["id"], {"devices": coordinator.devices})


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): AREAS_COMMAND})
@websocket_api.async_response
async def websocket_areas(hass, connection, msg):
    """Return aggregated area views; this endpoint never writes registries."""
    coordinator = hass.data["homekit_manager"]["coordinator"]
    connection.send_result(msg["id"], {"areas": coordinator.areas})


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): DIAGNOSTICS_COMMAND})
@websocket_api.async_response
async def websocket_diagnostics(hass, connection, msg):
    """Return read-only findings and recommendations."""
    coordinator = hass.data["homekit_manager"]["coordinator"]
    connection.send_result(msg["id"], coordinator.diagnostics())


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): DEVICE_PREVIEW_COMMAND, probatio.Required("entity_id"): str, probatio.Optional("options"): dict})
@websocket_api.async_response
async def websocket_device_preview(hass, connection, msg):
    """Return a simulated accessory view; never persists or applies options."""
    coordinator = hass.data["homekit_manager"]["coordinator"]
    entity = next((item for item in coordinator.inventory if item.get("entity_id") == msg["entity_id"]), None)
    if entity is None:
        connection.send_error(msg["id"], "not_found", "Entität nicht im aktuellen Inventar")
        return
    try:
        connection.send_result(msg["id"], build_preview(entity, msg.get("options")))
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_options", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): RULES_PREVIEW_COMMAND, probatio.Required("rules"): list, probatio.Optional("manual"): dict})
@websocket_api.async_response
async def websocket_rules_preview(hass, connection, msg):
    """Evaluate rule suggestions without saving or applying them."""
    coordinator = hass.data["homekit_manager"]["coordinator"]
    try:
        connection.send_result(msg["id"], evaluate_rules(coordinator.inventory, msg["rules"], msg.get("manual")))
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_rules", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): HISTORY_COMMAND})
@websocket_api.async_response
async def websocket_history(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    connection.send_result(msg["id"], coordinator.history())


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): HISTORY_RESTORE_COMMAND, probatio.Required("index"): int})
@websocket_api.async_response
async def websocket_history_restore(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    try:
        connection.send_result(msg["id"], coordinator.restore_history(msg["index"]))
    except ValueError as err:
        connection.send_error(msg["id"], "not_found", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): PERFORMANCE_COMMAND})
@websocket_api.async_response
async def websocket_performance(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    connection.send_result(msg["id"], summarize_inventory(coordinator.inventory) | {"last_updated": coordinator.last_updated, "refresh_duration_ms": coordinator.refresh_duration_ms, "refresh_count": coordinator.refresh_count, "snapshot_stale": bool(coordinator.last_error)} )


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): MODE_STATUS_COMMAND})
@websocket_api.async_response
async def websocket_mode_status(hass, connection, msg):
    """Return active and desired mode without changing HomeKit."""
    coordinator = hass.data["homekit_manager"]["coordinator"]
    connection.send_result(msg["id"], coordinator.mode_status())


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): SET_MODE_COMMAND, probatio.Required("mode"): str})
@websocket_api.async_response
async def websocket_set_mode(hass, connection, msg):
    """Persist a desired mode while keeping risky transitions blocked."""
    coordinator = hass.data["homekit_manager"]["coordinator"]
    try:
        connection.send_result(msg["id"], await coordinator.async_set_mode(msg["mode"]))
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_mode", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): MIGRATION_PLAN_COMMAND, probatio.Optional("target"): str})
@websocket_api.async_response
async def websocket_migration_plan(hass, connection, msg):
    """Return the storage assistant plan without changing any HA state."""
    coordinator = hass.data["homekit_manager"]["coordinator"]
    try:
        connection.send_result(msg["id"], coordinator.migration_plan(msg.get("target")))
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_mode", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): MIGRATION_STATUS_COMMAND})
@websocket_api.async_response
async def websocket_migration_status(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    connection.send_result(msg["id"], coordinator.migration_status_snapshot())


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): MIGRATION_START_COMMAND, probatio.Required("target"): str, probatio.Optional("confirmed"): bool, probatio.Optional("expected_entry_id"): str})
@websocket_api.async_response
async def websocket_migration_start(hass, connection, msg):
    """Verify a same-source mode or return a durable cross-source blocker."""
    coordinator = hass.data["homekit_manager"]["coordinator"]
    try:
        result = await coordinator.async_start_migration(msg["target"], bool(msg.get("confirmed", False)))
        connection.send_result(msg["id"], result)
    except ValueError as err:
        connection.send_error(msg["id"], "migration_blocked", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): MANAGEMENT_STATUS_COMMAND})
@websocket_api.async_response
async def websocket_management_status(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    connection.send_result(msg["id"], coordinator.management_status())


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): MANAGEMENT_ENABLE_COMMAND, probatio.Optional("confirmed"): bool, probatio.Optional("expected_entry_id"): str})
@websocket_api.async_response
async def websocket_management_enable(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    try:
        result = await coordinator.async_enable_management(bool(msg.get("confirmed", False)), msg.get("expected_entry_id"))
        connection.send_result(msg["id"], result)
    except (ValueError, OSError) as err:
        connection.send_error(msg["id"], "management_blocked", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): MANAGEMENT_DISABLE_COMMAND, probatio.Optional("confirmed"): bool, probatio.Optional("expected_entry_id"): str})
@websocket_api.async_response
async def websocket_management_disable(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    try:
        result = await coordinator.async_disable_management(bool(msg.get("confirmed", False)), msg.get("expected_entry_id"))
        connection.send_result(msg["id"], result)
    except (ValueError, OSError) as err:
        connection.send_error(msg["id"], "management_blocked", str(err))


def _document(msg):
    return msg.get("document") or msg.get("draft")


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): YAML_STATUS_COMMAND})
@websocket_api.async_response
async def websocket_yaml_status(hass, connection, msg):
    coordinator = hass.data["homekit_manager"]["coordinator"]
    try:
        connection.send_result(msg["id"], await coordinator.async_yaml_status())
    except YamlStoreError as err:
        connection.send_error(msg["id"], "storage_error", str(err))


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
        result = await coordinator.async_save_draft(_document(msg), msg.get("expected_file_version"), msg.get("expected_fingerprint"))
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
@websocket_api.websocket_command({
    probatio.Required("type"): APPLY_OPTIONS_DIFF_COMMAND,
    probatio.Required("document"): dict,
    probatio.Optional("expected_fingerprint"): str,
    probatio.Optional("request_id"): str,
})
@websocket_api.async_response
async def websocket_apply_options_diff(hass, connection, msg):
    """Apply only a freshly validated diff to a supported SOURCE_USER bridge."""
    coordinator = hass.data["homekit_manager"]["coordinator"]
    try:
        result = await coordinator.async_apply_options_diff(
            _document(msg), msg.get("expected_fingerprint"), msg.get("request_id")
        )
    except YamlVersionConflict as err:
        connection.send_error(msg["id"], "conflict", str(err))
        return
    except (YamlValidationError, HomeKitWriteError, ValueError) as err:
        connection.send_error(msg["id"], "write_blocked", str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.require_admin
@websocket_api.websocket_command({
    probatio.Required("type"): ACTIVATION_STATUS_COMMAND,
    probatio.Optional("entry_id"): str,
    probatio.Optional("request_id"): str,
})
@websocket_api.async_response
async def websocket_activation_status(hass, connection, msg):
    """Return the last known status without retrying or applying anything."""
    coordinator = hass.data["homekit_manager"]["coordinator"]
    connection.send_result(
        msg["id"],
        coordinator.activation_status(msg.get("entry_id"), msg.get("request_id")),
    )


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

REGISTERED_HANDLERS = (websocket_inventory, websocket_bridges, websocket_select_bridge, websocket_devices, websocket_areas, websocket_diagnostics, websocket_device_preview, websocket_rules_preview, websocket_history, websocket_history_restore, websocket_performance, websocket_activation_status, websocket_mode_status, websocket_set_mode, websocket_migration_plan, websocket_migration_status, websocket_migration_start, websocket_management_status, websocket_management_enable, websocket_management_disable, websocket_yaml_status, websocket_validate_draft, websocket_preview, websocket_save_draft, websocket_apply_options_diff, websocket_prepare_options_diff, websocket_reconcile, websocket_export)


def async_register_websocket_commands(hass, coordinator) -> None:
    """Register the complete authenticated API contract."""
    for handler in REGISTERED_HANDLERS:
        websocket_api.async_register_command(hass, handler)


def async_unregister_websocket_commands(hass) -> None:
    """Remove only handlers owned by this integration on entry unload."""
    registry = hass.data.get(websocket_api.DOMAIN, {})
    for handler in REGISTERED_HANDLERS:
        command = handler._ws_command
        if command in registry and registry[command][0] is handler:
            registry.pop(command)
