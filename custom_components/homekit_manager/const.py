"""Constants for HomeKit Manager."""
from __future__ import annotations
DOMAIN = "homekit_manager"
INTEGRATION_VERSION = "0.10.7"
INVENTORY_COMMAND = f"{DOMAIN}/inventory"
BULK_PREVIEW_COMMAND = f"{DOMAIN}/bulk_preview"
BRIDGES_COMMAND = f"{DOMAIN}/bridges"
SELECT_BRIDGE_COMMAND = f"{DOMAIN}/select_bridge"
YAML_STATUS_COMMAND = f"{DOMAIN}/yaml_status"
VALIDATE_DRAFT_COMMAND = f"{DOMAIN}/validate_draft"
PREVIEW_COMMAND = f"{DOMAIN}/preview"
SAVE_DRAFT_COMMAND = f"{DOMAIN}/save_draft"
PREPARE_OPTIONS_DIFF_COMMAND = f"{DOMAIN}/prepare_options_diff"
APPLY_OPTIONS_DIFF_COMMAND = f"{DOMAIN}/apply_options_diff"
OPERATION_PLAN_COMMAND = f"{DOMAIN}/operation_plan"
OPERATION_APPLY_COMMAND = f"{DOMAIN}/operation_apply"
OPERATION_STATUS_COMMAND = f"{DOMAIN}/operation_status"
OPERATION_RECONCILE_COMMAND = f"{DOMAIN}/operation_reconcile"
TEST_WRITE_MODE_ENABLE_COMMAND = f"{DOMAIN}/test_write_mode_enable"
TEST_WRITE_MODE_DISABLE_COMMAND = f"{DOMAIN}/test_write_mode_disable"
RECONCILE_COMMAND = f"{DOMAIN}/reconcile"
EXPORT_COMMAND = f"{DOMAIN}/export"
MODE_STATUS_COMMAND = f"{DOMAIN}/mode_status"
SET_MODE_COMMAND = f"{DOMAIN}/set_mode"
DEVICES_COMMAND = f"{DOMAIN}/devices"
AREAS_COMMAND = f"{DOMAIN}/areas"
DIAGNOSTICS_COMMAND = f"{DOMAIN}/diagnostics"
DEVICE_PREVIEW_COMMAND = f"{DOMAIN}/device_preview"
RULES_PREVIEW_COMMAND = f"{DOMAIN}/rules_preview"
HISTORY_COMMAND = f"{DOMAIN}/history"
HISTORY_RESTORE_COMMAND = f"{DOMAIN}/history_restore"
PERFORMANCE_COMMAND = f"{DOMAIN}/performance"
ACTIVATION_STATUS_COMMAND = f"{DOMAIN}/activation_status"
MIGRATION_PLAN_COMMAND = f"{DOMAIN}/migration_plan"
MIGRATION_START_COMMAND = f"{DOMAIN}/migration_start"
MIGRATION_STATUS_COMMAND = f"{DOMAIN}/migration_status"
MANAGEMENT_STATUS_COMMAND = f"{DOMAIN}/management_status"
MANAGEMENT_ENABLE_COMMAND = f"{DOMAIN}/management_enable"
MANAGEMENT_DISABLE_COMMAND = f"{DOMAIN}/management_disable"
SCHEMA_VERSION = 1
SUPPORTED_CORE_VERSION = "2026.10.4"
NATIVE_FILTER_WRITE_CORE_VERSIONS = frozenset({"2026.10.4", "2026.11.0b0"})
MODE_SCHEMA_VERSION = 1
HISTORY_SCHEMA_VERSION = 1
MAX_HISTORY_ENTRIES = 50
MODE_YAML = "yaml"
MODE_HOMEKIT_BRIDGE = "homekit_bridge"
MODE_HOMEKIT_MANAGER = "homekit_manager"
MANAGEMENT_MODES = (MODE_YAML, MODE_HOMEKIT_BRIDGE, MODE_HOMEKIT_MANAGER)
UNKNOWN = "unknown"
SUPPORTED_DOMAINS = frozenset({
    "alarm_control_panel", "automation", "binary_sensor", "button", "camera",
    "climate", "cover", "demo", "device_tracker", "fan", "humidifier",
    "input_boolean", "input_button", "input_select", "light", "lock",
    "media_player", "person", "remote", "scene", "script", "select", "sensor",
    "switch", "vacuum", "lawn_mower", "water_heater", "valve",
})

