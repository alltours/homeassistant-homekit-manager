"""Read-only comparison of Manager intent, native filter state, and runtime state."""
from __future__ import annotations

from collections import Counter
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


def _decision_entries(
    document: Mapping[str, Any], entry_id: str, inventory: list[Mapping[str, Any]],
    native_filter: Mapping[str, Any] | None,
    active_publication: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build one stable, explainable row for every reconciliation deviation.

    Legacy override documents intentionally do not reinterpret broad native
    rules as Manager intent.  Only explicit native entity includes are shown
    as unmanaged native decisions; domain/glob matches remain a separate
    source-level warning.  This makes the historical ``54 exclusions + 6
    native explicit includes`` case observable as 60 concrete rows instead of
    an unexplained aggregate.
    """
    policy, includes, excludes = _desired_ids(document, entry_id)
    by_id = {item.get("entity_id"): item for item in inventory if item.get("entity_id")}
    native_ids = _native_ids(inventory)
    native_explicit = {
        entity_id for entity_id in native_ids
        if (by_id.get(entity_id, {}).get("homekit", {}).get("filter_reason") == "explicit_include")
    }
    decisions = (document.get("bridges", {}).get(entry_id, {}) or {}).get("entities", {})
    rows: list[dict[str, Any]] = []

    def add(kind: str, entity_id: str | None, cause: str, *, severity: str = "warning", source: str = "manager") -> None:
        safe_id = entity_id or "<bridge>"
        rows.append({
            "id": f"{kind}:{safe_id}",
            "classification": kind,
            "entity_id": entity_id,
            "cause": cause,
            "severity": severity,
            "source": source,
        })

    for entity_id, status in sorted(decisions.items()):
        if status not in {"include", "exclude"}:
            add("invalid_manager_decision", entity_id, f"Ungültiger Manager-Status: {status!r}", severity="critical")
            continue
        if entity_id not in by_id:
            add("stale_manager_decision", entity_id, "Entity-ID ist im aktuellen Snapshot nicht vorhanden", severity="critical")
            continue
        if status == "include" and entity_id not in native_ids:
            add("manager_include_not_native", entity_id, "Explizit eingeschlossen, aber nicht durch den nativen Filter ausgewählt")
        if status == "exclude" and entity_id in native_ids:
            add("manager_exclude_native", entity_id, "Explizit ausgeschlossen, aber durch den nativen Filter ausgewählt", severity="critical")

    if policy != "positive_list":
        for entity_id in sorted(native_explicit - set(decisions)):
            add("native_explicit_unmanaged", entity_id,
                "Native Entity-Auswahl ist vorhanden, aber keine Manager-Entscheidung rekonstruiert werden kann",
                source="native")

    if policy == "positive_list":
        desired_ids = includes
        for entity_id in sorted(desired_ids - native_ids):
            add("desired_not_native", entity_id, "Positivlisten-Entscheidung fehlt im nativen Filter", severity="critical")
        for entity_id in sorted(native_ids - desired_ids):
            add("native_not_desired", entity_id, "Nativer Filter wählt eine Entity außerhalb der Positivliste aus", severity="critical", source="native")

    if active_publication.get("state") == "verified" and policy == "positive_list":
        runtime_ids = set(active_publication.get("entity_ids", []))
        desired_ids = includes
        for entity_id in sorted(runtime_ids - desired_ids):
            add("runtime_not_desired", entity_id, "Runtime-Accessory ist nicht Bestandteil der Positivliste", severity="critical", source="runtime")
        for entity_id in sorted(desired_ids - runtime_ids):
            add("desired_not_runtime", entity_id, "Positivlisten-Entity ist nicht als Runtime-Accessory nachgewiesen", source="runtime")

    return sorted(rows, key=lambda row: row["id"])


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
    native_explicit = {
        str(item["entity_id"]) for item in inventory
        if item.get("entity_id")
        and item.get("homekit", {}).get("configured_by_filter") is True
        and item.get("homekit", {}).get("filter_reason") == "explicit_include"
    }
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
    deviations = _decision_entries(document, entry_id, inventory, native_filter, active)
    mismatch = bool(deviations) or (policy == "positive_list" and not native_known)
    classification_counts = dict(sorted(Counter(row["classification"] for row in deviations).items()))
    return {
        "policy": policy,
        "manager": {
            "includes": sorted(includes),
            "excludes": sorted(excludes),
            "stale_decisions": sorted(
                row["entity_id"] for row in deviations
                if row["classification"] == "stale_manager_decision"
            ),
            "invalid_decisions": sorted(
                row["entity_id"] for row in deviations
                if row["classification"] == "invalid_manager_decision"
            ),
        },
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
            "explicit_entity_ids": sorted(native_explicit),
            "broad_rules": _broad_filter(native_filter),
        },
        "active": active,
        "differences": {
            "desired_not_native": added,
            "native_not_desired": removed,
            "unknown_entities": unknown,
            "count": len(deviations),
        },
        "deviations": deviations,
        "deviation_summary": classification_counts,
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
