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


_RECOMMENDATIONS = {
    "native_explicit_unmanaged": "Manager-Entscheidung fachlich prüfen; nicht automatisch übernehmen.",
    "stale_manager_decision": "Entity Registry und Historie prüfen; veraltete Entscheidung erst danach bereinigen.",
    "manager_include_not_native": "Native Filterauswahl und Manager-Entscheidung abgleichen; Apply bleibt gesperrt.",
    "manager_exclude_native": "Ausschlussentscheidung und native Auswahl prüfen; unbeabsichtigte Veröffentlichung ausschließen.",
    "invalid_manager_decision": "Ungültige Manager-Entscheidung manuell korrigieren; keine automatische Auswahlübernahme.",
    "desired_not_native": "Positivlisten-Entscheidung gegen den nativen Filter prüfen.",
    "native_not_desired": "Native Auswahl gegen die explizite Positivliste prüfen.",
    "runtime_not_desired": "Runtime-Accessory gegen die Positivliste prüfen; unerwartete Veröffentlichung blockieren.",
    "desired_not_runtime": "Runtime-Nachweis für die Positivlisten-Entity prüfen.",
}


# These classifications describe a real disagreement between a selection
# authority and another observed selection.  The remaining classifications are
# still unresolved and therefore block a later write, but they are metadata or
# evidence problems rather than proof that the native and desired sets differ.
_DIRECT_SELECTION_CONFLICTS = frozenset({
    "manager_include_not_native",
    "manager_exclude_native",
    "desired_not_native",
    "native_not_desired",
    "runtime_not_desired",
    "desired_not_runtime",
})


def _domain(entity_id: str | None) -> str | None:
    if not isinstance(entity_id, str) or "." not in entity_id:
        return None
    return entity_id.split(".", 1)[0] or None


def _runtime_rows(
    active_publication: Mapping[str, Any],
    runtime_diagnosis: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    rows = []
    if isinstance(runtime_diagnosis, Mapping):
        rows = runtime_diagnosis.get("accessories", []) or []
    if not rows and isinstance(active_publication, Mapping):
        rows = active_publication.get("accessories", []) or []
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        entity_id = row.get("entity_id") if isinstance(row, Mapping) else None
        if isinstance(entity_id, str) and entity_id not in result:
            result[entity_id] = row
    return result


def _decorate_deviation(
    row: Mapping[str, Any],
    by_id: Mapping[str, Mapping[str, Any]],
    decisions: Mapping[str, Any],
    active_publication: Mapping[str, Any],
    runtime_diagnosis: Mapping[str, Any] | None,
) -> dict[str, Any]:
    entity_id = row.get("entity_id")
    item = by_id.get(entity_id) if isinstance(entity_id, str) else None
    item = item if isinstance(item, Mapping) else {}
    homekit = item.get("homekit", {}) if isinstance(item.get("homekit", {}), Mapping) else {}
    runtime_statuses = active_publication.get("entity_status", {})
    if (not isinstance(runtime_statuses, Mapping) or not runtime_statuses) and runtime_diagnosis:
        runtime_statuses = runtime_diagnosis.get("entity_status", {})
    runtime_status = runtime_statuses.get(entity_id, "unknown") if isinstance(runtime_statuses, Mapping) else "unknown"
    runtime_row = _runtime_rows(active_publication, runtime_diagnosis).get(entity_id, {})
    manager_decision = decisions.get(entity_id) if isinstance(entity_id, str) else None
    if manager_decision not in {"include", "exclude"}:
        manager_decision = None

    evidence_sources = ["selection_reconciliation"]
    if item:
        evidence_sources.append("inventory_snapshot")
    if homekit.get("configured_by_filter") is not None:
        evidence_sources.append("native_config_entry_filter")
    if manager_decision is not None:
        evidence_sources.append("manager_draft")
    if runtime_status != "unknown":
        evidence_sources.append("runtime_hap_diagnosis")

    native_selection = homekit.get("configured_by_filter") if item else None
    unavailable_fields = []
    fields = {
        "device_id": item.get("device_id"),
        "device_name": item.get("device_name"),
        "area_id": item.get("area_id"),
        "area_name": item.get("area_name"),
        "aid": runtime_row.get("aid") if isinstance(runtime_row, Mapping) else None,
        "iid_signature": runtime_row.get("iid_signature") if isinstance(runtime_row, Mapping) else None,
    }
    unavailable_fields.extend(key for key, value in fields.items() if value is None)
    verification_status = "VERIFIED" if item and runtime_status != "unknown" else "PARTIAL" if item else "NOT_VERIFIED"

    classification = row.get("classification")
    severity = row.get("severity", "warning")
    security_relevance = {
        "critical": "HIGH",
        "warning": "MEDIUM",
        "info": "LOW",
    }.get(severity, "NOT_VERIFIED")
    return dict(row) | {
        "deviation_type": classification,
        "device_id": fields["device_id"],
        "device_name": fields["device_name"],
        "area_id": fields["area_id"],
        "area_name": fields["area_name"],
        "domain": item.get("domain") or _domain(entity_id),
        "native_selection": native_selection,
        "manager_decision": manager_decision,
        "runtime_selection": runtime_status,
        "hap_publication_status": runtime_status,
        "aid": fields["aid"],
        "iid_signature": fields["iid_signature"],
        "technical_cause": row.get("cause"),
        "security_relevance": security_relevance,
        "recommendation": _RECOMMENDATIONS.get(classification, "Einzelfall lesend prüfen; keine automatische Änderung."),
        "evidence_sources": evidence_sources,
        "verification_status": verification_status,
        "unavailable_fields": unavailable_fields,
    }


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
    runtime_diagnosis: Mapping[str, Any] | None = None,
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
    decisions = (document.get("bridges", {}).get(entry_id, {}) or {}).get("entities", {})
    by_id = {item.get("entity_id"): item for item in inventory if item.get("entity_id")}
    deviations = [
        _decorate_deviation(row, by_id, decisions, active, runtime_diagnosis)
        for row in deviations
    ]
    direct_conflicts = [
        row for row in deviations
        if row.get("classification") in _DIRECT_SELECTION_CONFLICTS
    ]
    selection_conflict = bool(
        direct_conflicts
        or added
        or removed
        or (policy == "positive_list" and not native_known)
    )
    mismatch = bool(deviations) or (policy == "positive_list" and not native_known)
    if selection_conflict:
        diagnostic_state = "selection_conflict"
    elif deviations:
        diagnostic_state = "metadata_unresolved"
    elif policy == "positive_list" and not native_known:
        diagnostic_state = "incomplete"
    else:
        diagnostic_state = "aligned"
    classification_counts = dict(sorted(Counter(row["classification"] for row in deviations).items()))
    if not mismatch and active.get("state") == "verified":
        message = "Manager-Auswahl, native Konfiguration und Laufzeitstatus stimmen überein."
    elif selection_conflict:
        message = "Die beobachteten Auswahlmengen widersprechen sich."
    elif deviations:
        message = "Die Auswahlmengen sind nicht direkt widersprüchlich; es bestehen ungeklärte Reconciliation-Metadaten."
    else:
        message = "Die native HomeKit-Konfiguration konnte nicht vollständig verglichen werden."
    return {
        "scope": "manager_native_runtime_selection",
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
        "selection_conflict": selection_conflict,
        "diagnostic_state": diagnostic_state,
        # Any unresolved row remains a write/migration blocker.  This is
        # intentionally separate from ``selection_conflict`` so a diagnostic
        # false positive cannot be fixed by weakening the safety gate.
        "migration_blocked": bool(deviations) or (policy == "positive_list" and not native_known),
        "blocking_reasons": [
            {
                "classification": row.get("classification"),
                "entity_id": row.get("entity_id"),
                "severity": row.get("severity"),
            }
            for row in deviations
        ] + ([{
            "classification": "native_snapshot_unavailable",
            "entity_id": None,
            "severity": "critical",
        }] if policy == "positive_list" and not native_known else []),
        "deviations": deviations,
        "deviation_summary": classification_counts,
        "deviation_count": len(deviations),
        "aligned": not mismatch,
        "state": "aligned" if not mismatch else "mismatch" if native_known else "unknown",
        "message": message,
    }
