"""Server-side, read-only desired-state change planning."""
from __future__ import annotations

from typing import Any, Mapping

from .yaml_store import validate_document
from .bulk import exclusion_reason

_FILTER_KEYS = {
    "include_entities", "exclude_entities", "include_domains", "exclude_domains",
    "include_entity_globs", "exclude_entity_globs",
}
_PATTERN_KEYS = {"include_domains", "exclude_domains", "include_entity_globs", "exclude_entity_globs"}


def _desired_for(document: Mapping[str, Any], entry_id: str) -> dict[str, str]:
    bridge = document.get("bridges", {}).get(entry_id, {})
    return dict(bridge.get("entities", {}))


def _current(item: Mapping[str, Any]) -> str:
    value = item.get("homekit", {}).get("configured_by_filter")
    if value is True:
        return "included"
    if value is False:
        return "excluded"
    return "unknown"


def _filter_assessment(bridge: Mapping[str, Any] | None) -> tuple[bool, str, bool]:
    config = (bridge or {}).get("filter")
    if config is None:
        return False, "HomeKit-Filter unbekannt", True
    unknown = set(config) - _FILTER_KEYS
    if unknown:
        return False, "Nicht unterstützte Filter-Schlüssel: " + ", ".join(sorted(unknown)), True
    patterns = sorted(key for key in config if key in _PATTERN_KEYS and config.get(key))
    if patterns:
        return True, "Bestehende Domain-/Glob-Regeln bleiben wirksam: " + ", ".join(patterns), False
    return False, "Explizite Filterregeln", False


def plan_changes(
    current_bridge: Mapping[str, Any] | None,
    desired_document: Mapping[str, Any],
    inventory: list[Mapping[str, Any]],
    expected_entry_id: str | None = None,
) -> dict[str, Any]:
    """Build a plan; this function has no side effects and never writes HA."""
    document = validate_document(desired_document)
    entry_id = expected_entry_id or (current_bridge or {}).get("entry_id")
    desired = _desired_for(document, entry_id or "")
    positive_list = document.get("bridges", {}).get(entry_id, {}).get("policy") == "positive_list"
    items = {item.get("entity_id"): item for item in inventory if item.get("entity_id")}
    pattern_rules, filter_reason, filter_unknown = _filter_assessment(current_bridge)
    changes: list[dict[str, Any]] = []
    incompatible = 0
    counts = {"new_includes": 0, "removed_includes": 0, "unchanged": 0, "unknown": 0, "conflicts": 0}

    for entity_id in sorted(set(items) | set(desired)):
        item = items.get(entity_id)
        requested = desired.get(entity_id)
        if item is None:
            counts["conflicts"] += 1
            counts["unknown"] += 1
            changes.append({"entity_id": entity_id, "current": "removed", "desired": requested or "unchanged", "action": "conflict", "risk": "high", "reason": "entity_removed", "blocked": True})
            continue
        current = _current(item)
        if current == "unknown":
            counts["unknown"] += 1
        desired_status = ("included" if requested == "include" else "excluded") if positive_list else ("included" if requested == "include" else "excluded" if requested == "exclude" else current)
        if positive_list and requested is None and current == "included":
            requested = "exclude"
        compat = item.get("compatibility", {}).get("status", "unknown")
        if compat == "unsupported" and requested == "include":
            incompatible += 1
            counts["conflicts"] += 1
            changes.append({"entity_id": entity_id, "current": current, "desired": desired_status, "action": "conflict", "risk": "high", "reason": "incompatible_entity", "blocked": True})
            continue
        if current == "unknown":
            if requested:
                counts["conflicts"] += 1
            changes.append({"entity_id": entity_id, "current": current, "desired": desired_status, "action": "conflict" if requested else "unknown", "risk": "high", "reason": "unknown_current_filter", "blocked": True})
            continue
        # A forged draft must not add an entity whose Core eligibility has
        # not been established. Existing includes remain untouched.
        if requested == "include" and current != "included":
            # A hidden entity is safe only when its exact Entity-ID is
            # explicitly present in the draft. Bulk scope previews keep the
            # conservative hidden-entity exclusion; this path is the later
            # exact include decision.
            unsafe = exclusion_reason(item, allow_hidden=requested == "include")
            if unsafe:
                counts["conflicts"] += 1
                changes.append({"entity_id": entity_id, "current": current, "desired": desired_status,
                                "action": "conflict", "risk": "high", "reason": unsafe, "blocked": True})
                continue
        if not requested or desired_status == current:
            counts["unchanged"] += 1
            changes.append({"entity_id": entity_id, "current": current, "desired": desired_status, "action": "unchanged", "risk": "low", "reason": "no_explicit_override", "blocked": False})
            continue
        if current == "unknown" or filter_unknown:
            counts["conflicts"] += 1
            changes.append({"entity_id": entity_id, "current": current, "desired": desired_status, "action": "conflict", "risk": "high", "reason": "unknown_current_filter", "blocked": True})
            continue
        action = "add" if desired_status == "included" else "remove"
        reason = "explicit_include" if action == "add" else "explicit_exclude"
        risk = "high" if pattern_rules or not item.get("available", True) else "low"
        changes.append({"entity_id": entity_id, "current": current, "desired": desired_status, "action": action, "risk": risk, "reason": reason, "blocked": False, "filter_impact": filter_reason if pattern_rules else None})
        counts["new_includes" if action == "add" else "removed_includes"] += 1

    return {
        "entry_id": entry_id,
        "changes": changes,
        "summary": counts | {"incompatible_entities": incompatible, "blocked": any(change["blocked"] for change in changes)},
        "filter_analysis": {"known": not filter_unknown, "pattern_rules": pattern_rules, "reason": filter_reason},
        "policy": "positive_list" if positive_list else "explicit_overrides",
    }
