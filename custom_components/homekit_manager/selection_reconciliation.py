"""Read-only comparison of Manager intent, native filter state, and runtime state."""
from __future__ import annotations

from typing import Any, Mapping


FILTER_KEYS = (
    "include_entities",
    "exclude_entities",
    "include_domains",
    "exclude_domains",
    "include_entity_globs",
    "exclude_entity_globs",
)


def _native_ids(inventory: list[Mapping[str, Any]]) -> set[str]:
    return {
        str(item["entity_id"])
        for item in inventory
        if item.get("entity_id") and item.get("homekit", {}).get("configured_by_filter") is True
    }


def _desired_ids(document: Mapping[str, Any], entry_id: str) -> tuple[str, set[str], set[str]]:
    bridge = document.get("bridges", {}).get(entry_id, {})
    entities = bridge.get("entities", {}) if isinstance(bridge, Mapping) else {}
    includes = {entity_id for entity_id, status in entities.items() if status == "include"}
    excludes = {entity_id for entity_id, status in entities.items() if status == "exclude"}
    return str(bridge.get("policy", "explicit_overrides")), includes, excludes


def _broad_filter(filter_config: Mapping[str, Any] | None) -> bool:
    config = filter_config or {}
    return any(config.get(key) for key in ("include_domains", "exclude_domains", "include_entity_globs", "exclude_entity_globs"))


def reconcile_selection(
    document: Mapping[str, Any],
    entry_id: str,
    inventory: list[Mapping[str, Any]],
    native_filter: Mapping[str, Any] | None,
    active_publication: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an explainable A/B/C comparison without changing any state.

    ``desired`` is the user's stored Manager intent (A), ``native`` is the
    effective Core filter selection (B), and ``active`` is the best available
    read-only runtime publication observation (C). For legacy override drafts,
    only explicitly recorded decisions are compared; unlisted entities remain
    intentionally ambiguous until migration is confirmed.
    """
    policy, includes, excludes = _desired_ids(document, entry_id)
    native_ids = _native_ids(inventory)
    if policy == "positive_list":
        desired_ids = includes
        added = sorted(desired_ids - native_ids)
        removed = sorted(native_ids - desired_ids)
        compared = sorted(desired_ids | native_ids)
    else:
        desired_ids = includes | excludes
        added = sorted(entity_id for entity_id in includes if entity_id not in native_ids)
        removed = sorted(entity_id for entity_id in excludes if entity_id in native_ids)
        compared = sorted(desired_ids)

    unknown = sorted(entity_id for entity_id in compared if not any(item.get("entity_id") == entity_id for item in inventory))
    native_known = native_filter is not None
    active = dict(active_publication or {"state": "unknown", "reason": "Keine Laufzeitprüfung durchgeführt"})
    mismatch = bool(added or removed or unknown) or (policy == "positive_list" and not native_known)
    return {
        "policy": policy,
        "desired": {
            "entity_count": len(desired_ids),
            "include_count": len(includes),
            "exclude_count": len(excludes),
            "entity_ids": sorted(desired_ids),
        },
        "native": {
            "known": native_known,
            "entity_count": len(native_ids),
            "entity_ids": sorted(native_ids),
            "broad_rules": _broad_filter(native_filter),
        },
        "active": active,
        "differences": {
            "desired_not_native": added,
            "native_not_desired": removed,
            "unknown_entities": unknown,
            "count": len(added) + len(removed) + len(unknown),
        },
        "aligned": not mismatch,
        "state": "aligned" if not mismatch else "mismatch" if native_known else "unknown",
        "message": (
            "Manager-Auswahl, native Konfiguration und Laufzeitstatus stimmen überein."
            if not mismatch and active.get("state") == "verified"
            else "Die Manager-Auswahl stimmt nicht mit der nativen HomeKit-Konfiguration überein."
            if mismatch
            else "Die native HomeKit-Konfiguration konnte nicht vollständig verglichen werden."
        ),
    }
