"""Conservative, side-effect-free eligibility for draft bulk actions."""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping


def exclusion_reason(item: Mapping[str, Any]) -> str | None:
    """Return the first reason an entity must stay out of automatic actions.

    This is intentionally stricter than Core's explicit include override. A
    manual single-entity decision remains separate from a bulk default.
    """
    if item.get("homekit", {}).get("configured_by_filter") is None:
        return "filter_unknown"
    if item.get("registry_entry_present") is not True:
        return "registry_missing"
    if item.get("device_id") and item.get("device_registry_status") in {"missing", "unknown"}:
        return "device_missing"
    if item.get("disabled_by") or item.get("device_disabled_by"):
        return "disabled"
    if item.get("hidden_by"):
        return "hidden"
    if item.get("entity_category") == "diagnostic":
        return "diagnostic"
    if item.get("entity_category") == "config":
        return "config"
    if item.get("entity_category"):
        return "entity_category"
    if item.get("state_present") is not True:
        return "no_state"
    status = item.get("compatibility", {}).get("status", "unknown")
    if status == "unsupported":
        return "unsupported"
    if status == "conditionally_supported":
        return "conditional"
    if status != "supported":
        return "compatibility_unknown"
    return None


def preview_bulk(
    inventory: list[Mapping[str, Any]], kind: str, key: str,
    *, entity_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Resolve the whole device/area on the server, independent of UI filters."""
    if kind == "device" and key.startswith("device:"):
        members = [item for item in inventory if item.get("device_id") == key[7:]]
    elif kind == "area" and (key.startswith("area:") or key.startswith("name:")):
        def area_key(item: Mapping[str, Any]) -> str:
            has_device = bool(item.get("device_id"))
            area_id = item.get("device_area_id") if has_device and "device_area_id" in item else item.get("area_id")
            area_name = item.get("device_area_name") if has_device and "device_area_id" in item else item.get("area_name")
            return f"area:{area_id}" if area_id else f"name:{area_name or 'Ohne Bereich'}"
        members = [item for item in inventory if area_key(item) == key]
    elif kind == "selection" and not key:
        if not isinstance(entity_ids, list) or any(type(value) is not str for value in entity_ids):
            raise ValueError("Ungültige Entitätsauswahl")
        selected = set(entity_ids)
        if not selected or len(selected) != len(entity_ids or []) or len(selected) > 10000:
            raise ValueError("Ungültige Entitätsauswahl")
        members = [item for item in inventory if item.get("entity_id") in selected]
        if len(members) != len(selected):
            raise ValueError("Auswahl enthält unbekannte Entitäten")
    else:
        raise ValueError("Unbekannter oder ungültiger Hierarchieknoten")
    if not members:
        raise ValueError("Der ausgewählte Knoten enthält keine Entitäten")
    reasons = Counter(reason for item in members if (reason := exclusion_reason(item)))
    eligible = [item["entity_id"] for item in members if exclusion_reason(item) is None]
    return {"total": len(members), "eligible_entity_ids": eligible,
            "skipped": dict(sorted(reasons.items())), "skipped_total": sum(reasons.values())}
