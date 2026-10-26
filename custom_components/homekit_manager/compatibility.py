"""Conservative, read-only HomeKit compatibility classification."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any, Mapping
from .const import SUPPORTED_DOMAINS

CORE_REFERENCE_VERSION = "2026.10.4"

@dataclass(frozen=True)
class Compatibility:
    status: str
    expected_type: str | None
    reason: str | None
    requirements: tuple[str, ...]
    def as_dict(self) -> dict[str, Any]:
        return asdict(self) | {"requirements": list(self.requirements)}


def compatibility_reference() -> dict[str, Any]:
    """Return the conservative, versioned compatibility reference used here."""
    return {
        "core_version": CORE_REFERENCE_VERSION,
        "supported_domains": sorted(SUPPORTED_DOMAINS),
        "unknown_domains": sorted(_KNOWN_UNCERTAIN_DOMAINS),
        "policy": "unknown_when_no_core_accessory_mapping_is_proven",
    }

_SIMPLE_TYPES = {
    "light": "Lightbulb", "switch": "Switch", "fan": "Fanv2", "cover": "WindowCovering",
    "lock": "LockMechanism", "vacuum": "RobotVacuum", "lawn_mower": "LawnMower",
    "humidifier": "HumidifierDehumidifier", "water_heater": "HeaterCooler",
    "alarm_control_panel": "SecuritySystem", "climate": "Thermostat",
    "camera": "CameraRTPStreamManagement", "media_player": "Television",
    "person": "OccupancySensor", "device_tracker": "OccupancySensor",
    "scene": "Switch", "script": "Switch", "automation": "Switch",
    "input_boolean": "Switch", "input_button": "StatelessProgrammableSwitch",
}
_SENSOR_TYPES = {
    "temperature": "TemperatureSensor", "humidity": "HumiditySensor", "battery": "BatteryService",
    "motion": "MotionSensor", "occupancy": "OccupancySensor", "presence": "OccupancySensor",
    "door": "ContactSensor", "window": "ContactSensor", "opening": "ContactSensor",
    "smoke": "SmokeSensor", "moisture": "LeakSensor", "carbon_monoxide": "CarbonMonoxideSensor",
    "carbon_dioxide": "CarbonDioxideSensor", "illuminance": "LightSensor", "pm25": "AirQualitySensor",
}
_BINARY_TYPES = {"motion", "occupancy", "presence", "door", "window", "opening", "smoke", "moisture", "problem", "safety", "connectivity"}
_KNOWN_UNCERTAIN_DOMAINS = {"number", "text", "time", "calendar", "image", "update", "notify", "zone", "counter", "input_number", "input_text", "event"}

def classify_entity(entity: Any, bridge_mode: str | None = None,
                    entity_config: Mapping[str, Any] | None = None) -> Compatibility:
    """Return a conservative classification; availability never means incompatibility."""
    if isinstance(entity, Mapping):
        domain = entity.get("domain")
        device_class = entity.get("device_class")
        attrs = entity.get("attributes", {}) or {}
    else:
        domain = getattr(entity, "domain", None)
        device_class = getattr(entity, "device_class", None)
        attrs = getattr(entity, "attributes", {}) or {}
    device_class = device_class or attrs.get("device_class")
    if domain in _KNOWN_UNCERTAIN_DOMAINS:
        return Compatibility("unknown", None, "Kein allgemeiner HomeKit-Accessory-Pfad aus der Domäne ableitbar.", ())
    if domain not in SUPPORTED_DOMAINS:
        return Compatibility("unsupported", None, "Die Domäne ist im HomeKit-Core nicht aufgeführt.", ())
    if domain == "binary_sensor" and device_class not in _BINARY_TYPES:
        return Compatibility("conditionally_supported", None, "Binary-Sensor ohne eindeutig unterstützte Device Class.", ("device_class",))
    if domain == "sensor":
        expected = _SENSOR_TYPES.get(device_class)
        if expected is None:
            return Compatibility("conditionally_supported", None, "Sensor-Device-Class nicht eindeutig HomeKit zuordenbar.", ("device_class", "unit_of_measurement"))
        return Compatibility("supported", expected, None, ())
    if domain in {"button", "select", "remote", "valve"}:
        expected = {"button": "StatelessProgrammableSwitch", "select": "Switch", "remote": "Remote", "valve": "Valve"}[domain]
        return Compatibility("conditionally_supported", expected, "Konkrete Entity-Fähigkeit muss zur Laufzeit geprüft werden.", ("runtime accessory creation",))
    expected = _SIMPLE_TYPES.get(domain)
    requirements: tuple[str, ...] = ()
    if domain == "camera":
        requirements = ("video stream", "codec/audio configuration")
    elif domain == "climate":
        requirements = ("supported HVAC modes",)
    elif domain in {"media_player", "lock", "cover"}:
        requirements = ("entity features",)
    if domain == "switch" and (entity_config or {}).get("type") == "outlet":
        expected = "Outlet"
    return Compatibility("supported", expected, None, requirements)

