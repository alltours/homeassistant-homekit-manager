"""Safe, non-persistent HomeKit device configuration previews."""
from __future__ import annotations

from typing import Any, Mapping

_EDITABLE_KEYS = {"name", "type"}

def supported_options(entity: Mapping[str, Any]) -> dict[str, Any]:
    """Describe only options that can be previewed without changing HomeKit."""
    expected = entity.get("compatibility", {}).get("expected_type")
    return {"fields": ["name", "type"], "default_type": expected, "type_options": [expected] if expected else [], "domain": entity.get("domain")}

def build_preview(entity: Mapping[str, Any], override: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build a clearly labelled simulation of a HomeKit service."""
    override = dict(override or {})
    invalid = sorted(set(override) - _EDITABLE_KEYS)
    if invalid:
        raise ValueError("Nicht unterstützte Vorschauoptionen: " + ", ".join(invalid))
    options = supported_options(entity)
    attributes = entity.get("attributes") or {}
    safe_attributes = {key: attributes[key] for key in ("unit_of_measurement", "device_class", "state_class") if key in attributes}
    return {
        "simulation": True,
        "entity_id": entity.get("entity_id"),
        "title": override.get("name") or entity.get("name") or entity.get("entity_id"),
        "service_type": override.get("type") or options["default_type"] or "Unbekannter Service",
        "domain": entity.get("domain"), "state": entity.get("state"),
        "attributes": safe_attributes, "options": options, "applied": False,
    }
