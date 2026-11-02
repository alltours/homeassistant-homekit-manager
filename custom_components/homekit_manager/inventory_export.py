"""Safe deterministic JSON/CSV exports of the current inventory snapshot."""
from __future__ import annotations

import csv
from io import StringIO
import json
from collections import Counter
from typing import Any, Mapping, Sequence


EXPORT_FIELDS = (
    "entity_id", "friendly_name", "domain", "device_id", "device_name",
    "area_id", "area_name", "integration", "entity_category", "hidden",
    "disabled", "availability", "available", "homekit_compatibility",
    "homekit_compatibility_reason", "native_filter_match", "native_filter_reason",
    "manager_decision", "runtime_publication",
)

RECONCILIATION_FIELDS = (
    "entity_id", "deviation_type", "device_id", "device_name", "area_id", "area_name", "domain",
    "native_selection", "manager_decision", "runtime_selection", "hap_publication_status", "aid",
    "iid_signature", "technical_cause", "severity", "security_relevance", "recommendation",
    "verification_status", "evidence_sources", "unavailable_fields",
)

TECHNICAL_FIELDS = (
    "code", "severity", "title", "detail", "entity_id", "filter_included", "published",
    "apple_home_visible", "recommendation",
)

RUNTIME_FIELDS = (
    "entity_id", "aid", "name", "mapping_source", "publication_status", "service_count",
    "characteristic_count", "iid_signature", "verification_status",
)


def _csv_value(value: Any) -> str:
    """Convert a value to CSV text and neutralise spreadsheet formulas."""
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, bool)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    else:
        text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _csv_content(fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> str:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_value(row.get(field)) for field in fields})
    return output.getvalue()


def _manager_decisions(document: Mapping[str, Any], entry_id: str | None) -> Mapping[str, str]:
    if not entry_id:
        return {}
    bridge = document.get("bridges", {}).get(entry_id, {})
    entities = bridge.get("entities", {}) if isinstance(bridge, Mapping) else {}
    return entities if isinstance(entities, Mapping) else {}


def _row(item: Mapping[str, Any], decisions: Mapping[str, str]) -> dict[str, Any]:
    homekit = item.get("homekit", {}) or {}
    compatibility = item.get("compatibility", {}) or {}
    entity_id = item.get("entity_id")
    decision = decisions.get(entity_id, "open")
    return {
        "entity_id": entity_id,
        "friendly_name": item.get("name"),
        "domain": item.get("domain"),
        "device_id": item.get("device_id"),
        "device_name": item.get("device_name"),
        "area_id": item.get("area_id"),
        "area_name": item.get("area_name"),
        "integration": item.get("integration_domain"),
        "entity_category": item.get("entity_category"),
        "hidden": bool(item.get("hidden_by")),
        "disabled": bool(item.get("disabled_by") or item.get("device_disabled_by")),
        "availability": item.get("availability_status", "unknown"),
        "available": bool(item.get("available")),
        "homekit_compatibility": compatibility.get("status", "unknown"),
        "homekit_compatibility_reason": compatibility.get("reason"),
        "native_filter_match": homekit.get("configured_by_filter"),
        "native_filter_reason": homekit.get("filter_reason", "unknown"),
        "manager_decision": decision if decision in {"include", "exclude"} else "open",
        "runtime_publication": homekit.get("runtime_publication", "unknown"),
    }


def build_inventory_export(
    inventory: Sequence[Mapping[str, Any]],
    overview: Mapping[str, Any],
    document: Mapping[str, Any],
    runtime_diagnosis: Mapping[str, Any],
) -> dict[str, Any]:
    """Build an exportable, value-free snapshot from one coordinator state."""
    entry_id = overview.get("selected_bridge_id")
    decisions = _manager_decisions(document, entry_id)
    rows = sorted((_row(item, decisions) for item in inventory), key=lambda item: item["entity_id"] or "")
    ids = [row["entity_id"] for row in rows]
    duplicate_ids = sorted(entity_id for entity_id, count in Counter(ids).items() if count > 1)
    checks = dict(overview.get("snapshot_checks", {}))
    checks.update({
        "export_entity_count": len(rows),
        "duplicate_export_entity_ids": duplicate_ids,
    })
    complete = bool(overview.get("snapshot_complete")) and not duplicate_ids
    return {
        "schema_version": 1,
        "generated_at": overview.get("snapshot_timestamp"),
        "snapshot_revision": overview.get("snapshot_revision"),
        "snapshot_fingerprint": overview.get("fingerprint"),
        "complete": complete,
        "completeness": checks,
        "bridge_entry_id": entry_id,
        "runtime_diagnosis": dict(runtime_diagnosis),
        "entities": rows,
    }


def export_inventory_snapshot(snapshot: Mapping[str, Any], format_name: str = "json") -> str:
    """Serialize a snapshot deterministically without state attributes."""
    if format_name == "json":
        return json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if format_name == "csv":
        return _csv_content(EXPORT_FIELDS, snapshot.get("entities", []))
    raise ValueError("Unbekanntes Inventar-Exportformat")


def _safe_bridge(bridges: Sequence[Mapping[str, Any]], entry_id: str | None) -> dict[str, Any] | None:
    bridge = next((item for item in bridges if item.get("entry_id") == entry_id), None)
    if not bridge:
        return None
    return {
        "entry_id": bridge.get("entry_id"),
        "title": bridge.get("title"),
        "source": bridge.get("source"),
        "state": bridge.get("state"),
        "mode": bridge.get("mode"),
        "name": bridge.get("name"),
        "port": bridge.get("port"),
        "filter": bridge.get("filter"),
    }


def _runtime_assignments(runtime_diagnosis: Mapping[str, Any]) -> list[dict[str, Any]]:
    assignments = []
    for row in runtime_diagnosis.get("accessories", []) or []:
        if not isinstance(row, Mapping):
            continue
        entity_id = row.get("entity_id")
        assignments.append({
            "entity_id": entity_id,
            "aid": row.get("aid"),
            "name": row.get("name"),
            "mapping_source": row.get("mapping_source", "unknown"),
            "publication_status": "published_verified" if isinstance(entity_id, str) else "unknown",
            "service_count": row.get("service_count"),
            "characteristic_count": row.get("characteristic_count"),
            "iid_signature": row.get("iid_signature"),
            "verification_status": "VERIFIED" if isinstance(entity_id, str) and row.get("mapping_source") != "unresolved" else "NOT_VERIFIED",
        })
    return sorted(assignments, key=lambda item: (item["entity_id"] or "", str(item["aid"] or "")))


def build_reconciliation_export(
    overview: Mapping[str, Any],
    bridges: Sequence[Mapping[str, Any]],
    diagnostics: Mapping[str, Any],
    runtime_diagnosis: Mapping[str, Any],
) -> dict[str, Any]:
    """Build one read-only, complete reconciliation/HAP evidence snapshot."""
    alignment = overview.get("configuration_alignment", {})
    deviations = []
    for source_row in alignment.get("deviations", []) or []:
        if not isinstance(source_row, Mapping):
            continue
        row = dict(source_row)
        for field in RECONCILIATION_FIELDS:
            row.setdefault(field, [] if field in {"evidence_sources", "unavailable_fields"} else None)
        if row.get("security_relevance") is None:
            row["security_relevance"] = {
                "critical": "HIGH",
                "warning": "MEDIUM",
                "info": "LOW",
            }.get(row.get("severity"), "NOT_VERIFIED")
        deviations.append(row)
    technical_findings = [dict(row) for row in diagnostics.get("findings", []) if isinstance(row, Mapping)]
    runtime_assignments = _runtime_assignments(runtime_diagnosis)
    deviation_count = alignment.get("deviation_count", 0)
    category_counts = dict(alignment.get("deviation_summary", {}))
    field_names = (
        "entity_id", "device_id", "device_name", "area_id", "area_name", "domain",
        "native_selection", "manager_decision", "runtime_selection", "hap_publication_status",
        "aid", "iid_signature",
    )
    missing_fields = sorted({
        field
        for row in deviations
        for field in field_names
        if row.get(field) is None
    })
    status_counts: dict[str, int] = {}
    for row in deviations:
        status = str(row.get("verification_status", "NOT_VERIFIED"))
        status_counts[status] = status_counts.get(status, 0) + 1
    runtime_baseline = dict(runtime_diagnosis.get("hap_baseline", {}))
    runtime_complete = runtime_diagnosis.get("completeness") == "verified"
    row_count_matches = len(deviations) == deviation_count
    runtime_assignment_rows_complete = runtime_complete and not runtime_diagnosis.get("ambiguous_accessories")
    export_complete = bool(overview.get("snapshot_complete")) and row_count_matches and runtime_assignment_rows_complete
    return {
        "schema_version": 2,
        "export_type": "homekit_manager_reconciliation",
        "manager_version": overview.get("integration_version"),
        "core_version": overview.get("core_version"),
        "snapshot_timestamp": overview.get("snapshot_timestamp"),
        "snapshot_revision": overview.get("snapshot_revision"),
        "snapshot_fingerprint": overview.get("fingerprint"),
        "complete": export_complete,
        "bridge": _safe_bridge(bridges, overview.get("selected_bridge_id")),
        "summary": {
            "selection_deviation_count": deviation_count,
            "selection_deviation_categories": category_counts,
            "technical_finding_count": len(technical_findings),
            "technical_finding_categories": dict(diagnostics.get("summary", {})),
            "runtime_accessory_count": runtime_diagnosis.get("accessory_count"),
            "runtime_mapped_accessory_count": runtime_diagnosis.get("mapped_accessory_count", 0),
            "runtime_ambiguous_accessory_count": runtime_diagnosis.get("ambiguous_accessory_count", 0),
            "runtime_entity_assignment_count": len(runtime_assignments),
        },
        "completeness": {
            "snapshot_complete": bool(overview.get("snapshot_complete")),
            "reconciliation_rows_complete": row_count_matches,
            "reconciliation_row_count": len(deviations),
            "reconciliation_expected_count": deviation_count,
            "runtime_complete": runtime_complete,
            "runtime_assignment_rows_complete": runtime_assignment_rows_complete,
            "complete": export_complete,
            "verification_status_counts": status_counts,
            "fields_with_not_verified_values": missing_fields,
        },
        "reconciliation": {
            "scope": alignment.get("scope"),
            "state": alignment.get("state"),
            "diagnostic_state": alignment.get("diagnostic_state"),
            "selection_conflict": alignment.get("selection_conflict"),
            "migration_blocked": alignment.get("migration_blocked"),
            "blocking_reasons": alignment.get("blocking_reasons", []),
            "policy": alignment.get("policy"),
            "message": alignment.get("message"),
            "differences": alignment.get("differences", {}),
            "deviations": deviations,
        },
        "technical_findings": technical_findings,
        "runtime": {
            "source": runtime_diagnosis.get("source"),
            "state": runtime_diagnosis.get("state"),
            "completeness": runtime_diagnosis.get("completeness"),
            "reason": runtime_diagnosis.get("reason"),
            "entry_id": runtime_diagnosis.get("entry_id"),
            "hap_baseline": runtime_baseline,
            "entity_status": dict(runtime_diagnosis.get("entity_status", {})),
            "entity_assignments": runtime_assignments,
            "service_count": runtime_diagnosis.get("service_count"),
            "characteristic_count": runtime_diagnosis.get("characteristic_count"),
            "accessory_count": runtime_diagnosis.get("accessory_count"),
            "mapped_accessory_count": runtime_diagnosis.get("mapped_accessory_count"),
            "ambiguous_accessory_count": runtime_diagnosis.get("ambiguous_accessory_count"),
        },
    }


def export_reconciliation_snapshot(snapshot: Mapping[str, Any], format_name: str = "json") -> dict[str, str]:
    """Serialize reconciliation data; CSV keeps technical/runtime rows separate."""
    if format_name == "json":
        return {"content": json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n"}
    if format_name != "csv":
        raise ValueError("Unbekanntes Reconciliation-Exportformat")
    reconciliation_rows = snapshot.get("reconciliation", {}).get("deviations", [])
    technical_rows = snapshot.get("technical_findings", [])
    runtime_rows = snapshot.get("runtime", {}).get("entity_assignments", [])
    return {
        "content": _csv_content(RECONCILIATION_FIELDS, reconciliation_rows),
        "technical_content": _csv_content(TECHNICAL_FIELDS, technical_rows),
        "runtime_content": _csv_content(RUNTIME_FIELDS, runtime_rows),
    }
