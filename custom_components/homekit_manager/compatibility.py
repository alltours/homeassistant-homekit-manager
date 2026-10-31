"""Side-effect-free projection of versioned HomeKit Core routing rules.

The native resolver also allocates accessory identities. We deliberately do not
call it: this module reports eligibility, never actual Apple Home publication.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from .const import SUPPORTED_CORE_VERSION, SUPPORTED_DOMAINS

CORE_REFERENCE_VERSION = SUPPORTED_CORE_VERSION
VERIFIED_COMPATIBILITY_VERSIONS = frozenset({"2026.10.4", "2026.11.0b0"})
_KNOWN_UNCERTAIN_DOMAINS = {"number", "text", "time", "calendar", "image", "update", "notify", "zone", "counter", "input_number", "input_text", "event"}

@dataclass(frozen=True)
class Compatibility:
    status: str
    expected_type: str | None
    reason: str | None
    requirements: tuple[str, ...] = ()

    def as_dict(self, core_version: str = CORE_REFERENCE_VERSION):
        return asdict(self) | {"requirements": list(self.requirements), "core_reference": core_version if core_version in VERIFIED_COMPATIBILITY_VERSIONS else None, "publication_verified": False}


def compatibility_reference():
    return {"core_version": CORE_REFERENCE_VERSION, "verified_versions": sorted(VERIFIED_COMPATIBILITY_VERSIONS), "supported_domains": sorted(SUPPORTED_DOMAINS), "unknown_domains": sorted(_KNOWN_UNCERTAIN_DOMAINS), "policy": "unknown_when_no_core_accessory_mapping_is_proven"}

_SIMPLE_TYPES = {"light": "Lightbulb", "switch": "Switch", "fan": "Fan", "lock": "LockMechanism", "vacuum": "Switch", "humidifier": "HumidifierDehumidifier", "water_heater": "WaterHeater", "alarm_control_panel": "SecuritySystem", "person": "OccupancySensor", "device_tracker": "OccupancySensor", "input_select": "SelectSwitch", "select": "SelectSwitch"}
_SENSOR_TYPES = {"temperature": "TemperatureSensor", "humidity": "HumiditySensor", "pm10": "PM10Sensor", "pm25": "PM25Sensor", "nitrogen_dioxide": "NitrogenDioxideSensor", "volatile_organic_compounds": "VolatileOrganicCompoundsSensor", "gas": "AirQualitySensor", "carbon_monoxide": "CarbonMonoxideSensor", "carbon_dioxide": "CarbonDioxideSensor", "illuminance": "LightSensor"}
_BINARY_TYPES = {"motion", "occupancy", "presence", "door", "window", "opening", "smoke", "moisture", "problem", "safety", "connectivity"}


def classify_entity(entity: Any, bridge_mode: str | None = "bridge", entity_config: Mapping[str, Any] | None = None, *, core_version: str = CORE_REFERENCE_VERSION) -> Compatibility:
    value = entity.get if isinstance(entity, Mapping) else lambda key, default=None: getattr(entity, key, default)
    domain = value("domain")
    attrs = value("attributes", {}) or {}
    device_class = value("device_class") or attrs.get("device_class")
    config = entity_config or {}
    if core_version not in VERIFIED_COMPATIBILITY_VERSIONS:
        return Compatibility("unknown", None, "Die HomeKit-Fähigkeiten dieser Core-Version sind nicht verifiziert.", (CORE_REFERENCE_VERSION,))
    if domain in _KNOWN_UNCERTAIN_DOMAINS:
        return Compatibility("unknown", None, "Kein allgemeiner Core-Accessory-Pfad nachgewiesen.")
    if domain not in SUPPORTED_DOMAINS or domain == "demo":
        return Compatibility("unsupported", None, "Für diese Domain erzeugt Core kein nachgewiesenes Accessory.")
    features = attrs.get("supported_features")
    features = features if type(features) is int else None
    from homeassistant.components.remote import RemoteEntityFeature
    accessory_required = domain in {"camera", "lock"} or (domain == "media_player" and device_class in {"tv", "receiver", "projector"}) or (domain == "remote" and bool((features or 0) & RemoteEntityFeature.ACTIVITY))
    if accessory_required and bridge_mode != "accessory":
        return Compatibility("unsupported" if bridge_mode == "bridge" else "conditionally_supported", None, "Diese Entität benötigt nach Core-Regeln den separaten Accessory-Modus.", ("accessory_mode",))
    if domain == "camera":
        return Compatibility("conditionally_supported", "Camera", "Stream und Codec sind noch nicht geprüft.", ("video stream", "codec/audio configuration"))
    if domain == "media_player":
        return Compatibility("conditionally_supported", "MediaPlayer", "Geräteklasse und Medienfunktionen müssen zu den Core-Regeln passen.", ("entity features",))
    if domain == "climate":
        return Compatibility("conditionally_supported", "Thermostat", "Thermostat-/HeaterCooler-Fähigkeiten werden erst durch Core aufgelöst.", ("supported HVAC modes",))
    if domain == "cover":
        from homeassistant.components.cover import CoverEntityFeature as F
        if features is None:
            return Compatibility("conditionally_supported", "WindowCovering", "Bewegungsfunktionen fehlen im aktuellen Zustand.", ("supported_features",))
        if not features & (F.OPEN | F.CLOSE | F.SET_POSITION | F.SET_TILT_POSITION):
            return Compatibility("unsupported", None, "Core kann ohne Bewegungsfunktion kein Cover-Accessory erzeugen.")
        return Compatibility("supported", "GarageDoorOpener" if device_class in {"garage", "gate"} and features & (F.OPEN | F.CLOSE) else "WindowCovering", None)
    if domain == "lawn_mower":
        from homeassistant.components.lawn_mower import LawnMowerEntityFeature as F
        if features is None:
            return Compatibility("conditionally_supported", "LawnMower", "Mäh- und Dockingfunktionen sind nicht verifiziert.", ("supported_features",))
        if not features & F.DOCK or not features & F.START_MOWING:
            return Compatibility("unsupported", None, "Core benötigt Docking und Mähstart.")
        return Compatibility("supported", "LawnMower", None)
    if domain == "sensor":
        unit = attrs.get("unit_of_measurement")
        expected = _SENSOR_TYPES.get(device_class)
        if core_version == "2026.11.0b0" and device_class in {"ozone", "sulphur_dioxide"}:
            expected = {"ozone": "OzoneSensor", "sulphur_dioxide": "SulphurDioxideSensor"}[device_class]
        if device_class == "temperature" or unit in {"°C", "°F"}:
            expected = "TemperatureSensor"
        if device_class == "illuminance" or unit == "lx":
            expected = "LightSensor"
        if device_class == "humidity" and unit != "%":
            return Compatibility("conditionally_supported", expected, "Core benötigt für Feuchte die Einheit %.", ("unit_of_measurement",))
        if not expected:
            return Compatibility("conditionally_supported", None, "Kein eindeutiger eigenständiger Core-Sensortyp; verknüpfte Batteriewerte sind kein eigenes Accessory.", ("device_class", "unit_of_measurement"))
        return Compatibility("supported", expected, None)
    if domain == "binary_sensor":
        return Compatibility("supported" if device_class in _BINARY_TYPES else "conditionally_supported", "BinarySensor", None if device_class in _BINARY_TYPES else "Die konkrete Sensorabbildung ist noch zu prüfen.")
    if domain in {"automation", "button", "input_boolean", "input_button", "remote", "scene", "script"}:
        return Compatibility("supported", "Switch", None)
    if domain == "valve":
        return Compatibility("conditionally_supported", "Valve", "Die konkrete Ventilfunktion ist noch zu prüfen.", ("entity features",))
    expected = _SIMPLE_TYPES.get(domain)
    if domain == "switch" and (config.get("type") == "outlet" or device_class == "outlet"):
        expected = "Outlet"
    return Compatibility("supported" if expected else "unknown", expected, None if expected else "Kein eindeutiger Core-Typ.")
