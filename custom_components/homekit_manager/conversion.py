"""Value conversion only: never migrate an existing HAP identity or pairing."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping


class ConversionBlocked(ValueError):
    """An unknown or unsupported field would be lost."""


_DATA = frozenset({"name", "port", "ip_address", "advertise_ip"})
_OPTIONS = frozenset({"filter", "entity_config", "mode", "devices"})
_FILTER = frozenset({"include_entities", "exclude_entities", "include_domains", "exclude_domains", "include_entity_globs", "exclude_entity_globs"})
_SUPPORTED_VERSION = "2026.10.4"


@dataclass(frozen=True)
class ConvertedValues:
    data: dict[str, Any]
    options: dict[str, Any]
    field_status: dict[str, str]
    core_version: str
    identity_preserved: bool = False
    pairing_preserved: bool = False

    def yaml_bridge(self) -> dict[str, Any]:
        return deepcopy(self.data | self.options)


def _check(value: Mapping[str, Any], core_version: str) -> None:
    if core_version != _SUPPORTED_VERSION:
        raise ConversionBlocked("Core-Version wurde für die Feldkonvertierung nicht geprüft")
    unknown = set(value) - _DATA - _OPTIONS
    if unknown:
        raise ConversionBlocked(f"Nicht übertragbare oder unbekannte Felder: {', '.join(sorted(unknown))}")
    filt = value.get("filter", {})
    if not isinstance(filt, Mapping) or set(filt) - _FILTER:
        raise ConversionBlocked("Unbekannte HomeKit-Filterfelder")
    for key, choices in filt.items():
        if not isinstance(choices, list) or any(not isinstance(item, str) for item in choices):
            raise ConversionBlocked(f"Filterfeld {key} ist keine Stringliste")
    from homeassistant.components.homekit import CONFIG_SCHEMA
    try:
        CONFIG_SCHEMA({"homekit": [dict(value)]})
    except Exception as err:
        raise ConversionBlocked("HomeKit-Core-Schema lehnt die Werte ab") from err


def native_to_yaml(data: Mapping[str, Any], options: Mapping[str, Any], *, core_version: str) -> ConvertedValues:
    """Project native entry values to YAML, without touching source or Entry ID."""
    if set(data) & set(options):
        raise ConversionBlocked("Gleichnamiges Feld in Config-Entry data und options")
    if set(data) - _DATA or set(options) - _OPTIONS:
        raise ConversionBlocked("Native Feldlage oder unbekannte Felder sind nicht übertragbar")
    value = deepcopy(dict(data) | dict(options))
    _check(value, core_version)
    return ConvertedValues(deepcopy(dict(data)), deepcopy(dict(options)), {key: "identisch" for key in value}, core_version)


def yaml_to_native(bridge: Mapping[str, Any], *, core_version: str) -> ConvertedValues:
    """Project YAML values to a *new* native entry's data/options shape."""
    value = deepcopy(dict(bridge))
    _check(value, core_version)
    data = {key: value[key] for key in value if key in _DATA}
    options = {key: value[key] for key in value if key in _OPTIONS}
    return ConvertedValues(data, options, {key: "identisch" for key in value}, core_version)
