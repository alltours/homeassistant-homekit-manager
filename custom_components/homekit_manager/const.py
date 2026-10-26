"""Constants for HomeKit Manager."""
from __future__ import annotations
DOMAIN = "homekit_manager"
INVENTORY_COMMAND = f"{DOMAIN}/inventory"
BRIDGES_COMMAND = f"{DOMAIN}/bridges"
YAML_STATUS_COMMAND = f"{DOMAIN}/yaml_status"
VALIDATE_DRAFT_COMMAND = f"{DOMAIN}/validate_draft"
PREVIEW_COMMAND = f"{DOMAIN}/preview"
SAVE_DRAFT_COMMAND = f"{DOMAIN}/save_draft"
PREPARE_OPTIONS_DIFF_COMMAND = f"{DOMAIN}/prepare_options_diff"
RECONCILE_COMMAND = f"{DOMAIN}/reconcile"
EXPORT_COMMAND = f"{DOMAIN}/export"
SCHEMA_VERSION = 1
UNKNOWN = "unknown"
SUPPORTED_DOMAINS = frozenset({
    "alarm_control_panel", "automation", "binary_sensor", "button", "camera",
    "climate", "cover", "demo", "device_tracker", "fan", "humidifier",
    "input_boolean", "input_button", "input_select", "light", "lock",
    "media_player", "person", "remote", "scene", "script", "select", "sensor",
    "switch", "vacuum", "lawn_mower", "water_heater", "valve",
})

