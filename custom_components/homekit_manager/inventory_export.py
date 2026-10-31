"""Safe deterministic JSON/CSV exports of the current inventory snapshot."""
from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from io import StringIO
from typing import Any

EXPORT_FIELDS = (
    "entity_id", "friendly_name", "domain", "device_id", "device_name",
    "area_id", "area_name", "integration", "entity_category", "hidden",
    "disabled", "availability", "available", "homekit_compatibility",
    "homekit_compatibility_reason", "native_filter_match", "native_filter_reason",
    "manager_decision", "runtime_publication",
)


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
        output = StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(snapshot.get("entities", []))
        return output.getvalue()
    raise ValueError("Unbekanntes Inventar-Exportformat")
