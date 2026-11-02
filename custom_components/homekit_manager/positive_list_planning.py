"""Pure, read-only planning for a future explicit HomeKit positive list.

This module deliberately does not accept a Home Assistant object and has no
write-capable dependencies.  It consumes an exported reconciliation snapshot
and a separately versioned, user-approved target list.  A plan can therefore
be generated offline without treating the target as a Manager decision.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any


PLAN_SCHEMA_VERSION = 1
_SUPPORTED_HISTORICAL_SCHEMA_VERSIONS = frozenset({1, 2})
_KNOWN_RUNTIME_STATUSES = frozenset({"published_verified", "published", "unknown"})


def _normalise_ids(entity_ids: Iterable[str]) -> tuple[list[str], list[str]]:
    values = list(entity_ids)
    invalid_values = [
        value for value in values
        if not isinstance(value, str)
        or "." not in value
        or not value.split(".", 1)[0]
        or not value.split(".", 1)[1]
        or any(token in value for token in ("*", "?", "[", "]"))
    ]
    invalid = sorted({str(value) for value in invalid_values})
    valid = sorted({value for value in values if isinstance(value, str) and value not in invalid_values})
    duplicates = sorted({value for value in values if isinstance(value, str) and values.count(value) > 1})
    return valid, sorted(set(invalid + duplicates))


def build_positive_list_plan(
    approved_entity_ids: Sequence[str],
    snapshot: Mapping[str, Any],
    *,
    target_source: str = "user_explicit_decision",
) -> dict[str, Any]:
    """Build a deterministic plan without changing any external state.

    The plan is intentionally conservative.  It proves an entity only when it
    is observed in the native filter/runtime evidence and treats every missing
    or incomplete input as a blocker.  Stale native references are removed
    from the current native set only when the snapshot contains an explicit
    stale-filter finding for that exact ID.
    """
    target_ids, target_errors = _normalise_ids(approved_entity_ids)
    raw_reconciliation = snapshot.get("reconciliation", {})
    reconciliation = raw_reconciliation if isinstance(raw_reconciliation, Mapping) else {}
    bridge = snapshot.get("bridge") or {}
    bridge = bridge if isinstance(bridge, Mapping) else {}
    filter_config = bridge.get("filter") or {}
    filter_config = filter_config if isinstance(filter_config, Mapping) else {}
    if not isinstance(raw_reconciliation, Mapping):
        malformed_reconciliation = True
    else:
        malformed_reconciliation = False
    native_filter_ids = set(filter_config.get("include_entities") or [])
    raw_technical = snapshot.get("technical_findings", []) or []
    technical = [row for row in raw_technical if isinstance(row, Mapping)] if isinstance(raw_technical, list) else []
    stale_filter_ids = {
        row.get("entity_id") for row in technical
        if row.get("code") == "stale_filter_reference" and isinstance(row.get("entity_id"), str)
    }
    current_native_ids = native_filter_ids - stale_filter_ids
    runtime = snapshot.get("runtime") or {}
    runtime = runtime if isinstance(runtime, Mapping) else {}
    raw_assignments = runtime.get("entity_assignments", []) or []
    assignments = [row for row in raw_assignments if isinstance(row, Mapping)] if isinstance(raw_assignments, list) else []
    runtime_ids = {row.get("entity_id") for row in assignments if isinstance(row.get("entity_id"), str)}
    runtime_status = runtime.get("entity_status") or {}
    raw_deviations = reconciliation.get("deviations", []) or []
    deviations = [row for row in raw_deviations if isinstance(row, Mapping)] if isinstance(raw_deviations, list) else []
    observed_present_ids = {
        row.get("entity_id") for row in deviations
        if isinstance(row.get("entity_id"), str)
        and (row.get("native_selection") is not None or row.get("runtime_selection") not in {None, "unknown"})
    } | current_native_ids | runtime_ids

    completeness = snapshot.get("completeness") or {}
    completeness = completeness if isinstance(completeness, Mapping) else {}
    blocking_reasons: list[dict[str, Any]] = []

    def block(reason_code: str, detail: str, **extra: Any) -> None:
        blocking_reasons.append({"code": reason_code, "detail": detail, **extra})

    if not target_ids:
        block("empty_target", "Die Soll-Auswahl darf nicht leer sein.")
    for error in target_errors:
        block("invalid_target_id", "Entity-ID ist ungültig, doppelt oder enthält eine Wildcard.", entity_id=error)
    if not snapshot.get("complete") or not completeness.get("snapshot_complete"):
        block("incomplete_snapshot", "Der Snapshot ist nicht vollständig.")
    if malformed_reconciliation or not isinstance(raw_deviations, list):
        block("malformed_reconciliation", "Die Reconciliation-Struktur oder ihre Zeilen sind ungültig.")
    if isinstance(raw_deviations, list) and any(not isinstance(row, Mapping) for row in raw_deviations):
        block("malformed_reconciliation_rows", "Reconciliation enthält nicht strukturierte Zeilen.")
    if not isinstance(raw_technical, list):
        block("malformed_technical_findings", "Die technischen Befunde haben einen ungültigen Datentyp.")
    if isinstance(raw_technical, list) and any(not isinstance(row, Mapping) for row in raw_technical):
        block("malformed_technical_rows", "Technische Befunde enthalten nicht strukturierte Zeilen.")
    if not isinstance(raw_assignments, list):
        block("malformed_runtime_assignments", "Die Runtime-Zuordnungen haben einen ungültigen Datentyp.")
    if isinstance(raw_assignments, list) and any(not isinstance(row, Mapping) for row in raw_assignments):
        block("malformed_runtime_rows", "Runtime-Zuordnungen enthalten nicht strukturierte Zeilen.")
    if not isinstance(runtime_status, Mapping):
        block("malformed_runtime_status", "Die Runtime-Statusstruktur hat einen ungültigen Datentyp.")
        runtime_status = {}
    schema_version = snapshot.get("schema_version")
    if schema_version not in _SUPPORTED_HISTORICAL_SCHEMA_VERSIONS:
        block("unsupported_schema", "Die Export-Schema-Version ist unbekannt.", schema_version=schema_version)
    elif schema_version != 2:
        block("historical_schema", "Schema-1-Daten sind historische Evidenz und keine aktuelle Migrationsfreigabe.", schema_version=schema_version)
    if schema_version == 2 and any(
        key not in reconciliation for key in ("selection_conflict", "diagnostic_state", "migration_blocked", "differences")
    ):
        block("missing_reconciliation_semantics", "Schema 2 enthält nicht alle Konflikt- und Blockierungsfelder.")
    if not completeness.get("reconciliation_rows_complete"):
        block("incomplete_reconciliation", "Die Reconciliation-Zeilen sind unvollständig.")
    if not completeness.get("runtime_complete") or not completeness.get("runtime_assignment_rows_complete"):
        block("incomplete_runtime", "Die Runtime-Zuordnung ist nicht vollständig verifiziert.")
    if not filter_config.get("include_entities") or any(
        filter_config.get(key) for key in filter_config if key != "include_entities"
    ):
        block("unsafe_native_filter", "Ein leerer oder breiter nativer Filter ist keine sichere Positivliste.")
    if reconciliation.get("selection_conflict") or reconciliation.get("diagnostic_state") == "selection_conflict":
        block("selection_conflict", "Ein echter Auswahlkonflikt ist ungeklärt.")
    if reconciliation.get("diagnostic_state") in {"metadata_unresolved", "incomplete"} or reconciliation.get("migration_blocked") is True:
        block("unresolved_reconciliation_metadata", "Reconciliation-Metadaten oder Snapshot-Evidenz sind ungeklärt.")
    for row in deviations:
        if row.get("severity") == "critical":
            block(
                "critical_reconciliation_deviation",
                "Eine kritische Reconciliation-Abweichung ist ungeklärt.",
                entity_id=row.get("entity_id"),
                classification=row.get("classification"),
            )
    for row in technical:
        if row.get("severity") == "critical":
            block(
                "critical_technical_finding",
                "Ein kritischer technischer Befund ist ungeklärt.",
                code=row.get("code"),
                entity_id=row.get("entity_id"),
            )
        if row.get("code") == "stale_filter_reference":
            block(
                "stale_filter_reference",
                "Eine native Filterreferenz ist veraltet und vor der Migration ungeklärt.",
                entity_id=row.get("entity_id"),
            )

    summary = snapshot.get("summary") or {}
    summary = summary if isinstance(summary, Mapping) else {}
    if summary.get("selection_deviation_count") is not None and summary.get("selection_deviation_count") != len(deviations):
        block("reconciliation_count_mismatch", "Reconciliation-Summe und exportierte Zeilen widersprechen sich.")
    if summary.get("technical_finding_count") is not None and summary.get("technical_finding_count") != len(technical):
        block("technical_count_mismatch", "Technische Summe und exportierte Befunde widersprechen sich.")
    if summary.get("runtime_entity_assignment_count") is not None and summary.get("runtime_entity_assignment_count") != len(assignments):
        block("runtime_count_mismatch", "Runtime-Summe und exportierte Zuordnungen widersprechen sich.")
    assignment_ids = [row.get("entity_id") for row in assignments]
    if len(assignment_ids) != len(set(assignment_ids)):
        block("duplicate_runtime_assignment", "Runtime-Zuordnungen enthalten doppelte Entity-IDs.")
    unknown_runtime_statuses = sorted({
        value for value in runtime_status.values()
        if value not in _KNOWN_RUNTIME_STATUSES
    }, key=str)
    if unknown_runtime_statuses:
        block("unknown_runtime_status", "Runtime enthält einen unbekannten Status.", statuses=unknown_runtime_statuses)

    unknown_target_ids = sorted(set(target_ids) - observed_present_ids)
    for entity_id in unknown_target_ids:
        block("target_not_observed", "Soll-Entity ist im aktuellen Snapshot nicht nachgewiesen.", entity_id=entity_id)

    assignment_by_id = {row.get("entity_id"): row for row in assignments if isinstance(row.get("entity_id"), str)}
    for entity_id in sorted(set(target_ids) & set(runtime_ids)):
        assignment = assignment_by_id.get(entity_id, {})
        if assignment.get("aid") is None or assignment.get("iid_signature") is None:
            block("missing_hap_identity", "Für eine Soll-Entity fehlt die HAP-AID/IID-Evidenz.", entity_id=entity_id)

    unexpected_native_ids = sorted(current_native_ids - set(target_ids))
    for entity_id in unexpected_native_ids:
        block("native_entity_outside_target", "Native Auswahl enthält eine nicht freigegebene aktuelle Entity.", entity_id=entity_id)

    rows: list[dict[str, Any]] = []
    for entity_id in target_ids:
        native_selected = entity_id in current_native_ids
        runtime_value = runtime_status.get(entity_id, "unknown")
        published = runtime_value in {"published_verified", "published"}
        status = "KEEP" if native_selected and published else "REVIEW_REQUIRED"
        if not native_selected:
            expected_change = "new_publication"
        elif not published:
            expected_change = "runtime_not_verified"
        else:
            expected_change = "unchanged"
        rows.append({
            "entity_id": entity_id,
            "native_selected": native_selected,
            "runtime_status": runtime_value,
            "runtime_published": published,
            "desired": "INCLUDE",
            "status": status,
            "expected_change": expected_change,
            "expected_accessory_effect": "none" if expected_change == "unchanged" else "not_verified",
            "aid": next((row.get("aid") for row in assignments if row.get("entity_id") == entity_id), None),
            "iid_signature": next((row.get("iid_signature") for row in assignments if row.get("entity_id") == entity_id), None),
            "verification_status": "VERIFIED" if native_selected and published else "NOT_VERIFIED",
        })

    unchanged = [row["entity_id"] for row in rows if row["expected_change"] == "unchanged"]
    new_publications = [row["entity_id"] for row in rows if row["expected_change"] == "new_publication"]
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "plan_type": "homekit_manager_positive_list_read_only_plan",
        "planning_only": True,
        "write_performed": False,
        "target_source": target_source,
        "bridge": {
            "entry_id": bridge.get("entry_id"),
            "mac": (runtime.get("hap_baseline") or {}).get("mac"),
            "port": bridge.get("port") or (runtime.get("hap_baseline") or {}).get("port"),
        },
        "target": {
            "entity_ids": target_ids,
            "count": len(target_ids),
            "allow_wildcards": False,
            "allow_domain_rules": False,
            "auto_extend": False,
        },
        "summary": {
            "keep": len(unchanged),
            "new_publications": len(new_publications),
            "desired_accessory_removals": 0,
            "review_required": sum(row["status"] == "REVIEW_REQUIRED" for row in rows),
            "blocking_reason_count": len(blocking_reasons),
        },
        "entities": rows,
        "expected_removals": [],
        "expected_new_publications": new_publications,
        "unchanged_entities": unchanged,
        "blocking_reasons": blocking_reasons,
        "migration_ready": not blocking_reasons and all(row["status"] == "KEEP" for row in rows),
        "open_risks": [
            "Produktive Filter- oder Manager-Entscheidungen wurden nicht verändert.",
            "Ein diagnostisch vollständiger Snapshot beweist keinen Apple-Home-Reconnect.",
        ],
    }
