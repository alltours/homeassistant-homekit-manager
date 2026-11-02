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
_SELECTION_STATUSES = frozenset({"published_verified", "published", "unknown"})


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
    reconciliation = snapshot.get("reconciliation", {})
    bridge = snapshot.get("bridge") or {}
    filter_config = bridge.get("filter") or {}
    native_filter_ids = set(filter_config.get("include_entities") or [])
    technical = [row for row in snapshot.get("technical_findings", []) or [] if isinstance(row, Mapping)]
    stale_filter_ids = {
        row.get("entity_id") for row in technical
        if row.get("code") == "stale_filter_reference" and isinstance(row.get("entity_id"), str)
    }
    current_native_ids = native_filter_ids - stale_filter_ids
    runtime = snapshot.get("runtime") or {}
    assignments = [row for row in runtime.get("entity_assignments", []) or [] if isinstance(row, Mapping)]
    runtime_ids = {row.get("entity_id") for row in assignments if isinstance(row.get("entity_id"), str)}
    runtime_status = runtime.get("entity_status") or {}
    deviations = [row for row in reconciliation.get("deviations", []) or [] if isinstance(row, Mapping)]
    observed_present_ids = {
        row.get("entity_id") for row in deviations
        if isinstance(row.get("entity_id"), str)
        and (row.get("native_selection") is not None or row.get("runtime_selection") not in {None, "unknown"})
    } | current_native_ids | runtime_ids

    completeness = snapshot.get("completeness") or {}
    blocking_reasons: list[dict[str, Any]] = []

    def block(reason_code: str, detail: str, **extra: Any) -> None:
        blocking_reasons.append({"code": reason_code, "detail": detail, **extra})

    if not target_ids:
        block("empty_target", "Die Soll-Auswahl darf nicht leer sein.")
    for error in target_errors:
        block("invalid_target_id", "Entity-ID ist ungültig, doppelt oder enthält eine Wildcard.", entity_id=error)
    if not snapshot.get("complete") or not completeness.get("snapshot_complete"):
        block("incomplete_snapshot", "Der Snapshot ist nicht vollständig.")
    if not completeness.get("reconciliation_rows_complete"):
        block("incomplete_reconciliation", "Die Reconciliation-Zeilen sind unvollständig.")
    if not completeness.get("runtime_complete") or not completeness.get("runtime_assignment_rows_complete"):
        block("incomplete_runtime", "Die Runtime-Zuordnung ist nicht vollständig verifiziert.")
    if not filter_config.get("include_entities") or any(
        filter_config.get(key) for key in (
            "include_domains", "exclude_domains", "include_entity_globs", "exclude_entity_globs",
        )
    ):
        block("unsafe_native_filter", "Ein leerer oder breiter nativer Filter ist keine sichere Positivliste.")
    if reconciliation.get("selection_conflict") or reconciliation.get("diagnostic_state") == "selection_conflict":
        block("selection_conflict", "Ein echter Auswahlkonflikt ist ungeklärt.")
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

    unknown_target_ids = sorted(set(target_ids) - observed_present_ids)
    for entity_id in unknown_target_ids:
        block("target_not_observed", "Soll-Entity ist im aktuellen Snapshot nicht nachgewiesen.", entity_id=entity_id)

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
