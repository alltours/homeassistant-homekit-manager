"""Read-only reconciliation after a user edits HomeKit manually."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def reconcile_desired_state(
    desired_document: Mapping[str, Any],
    entry_id: str,
    inventory: list[Mapping[str, Any]],
    *,
    baseline_fingerprint: str | None = None,
    current_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Compare explicit desired overrides with the currently observed filter."""
    desired = desired_document.get("bridges", {}).get(entry_id, {}).get("entities", {})
    by_id = {item.get("entity_id"): item for item in inventory if item.get("entity_id")}
    results = []
    satisfied = open_count = unknown = 0
    for entity_id in sorted(desired):
        wanted = "included" if desired[entity_id] == "include" else "excluded"
        item = by_id.get(entity_id)
        observed = None if item is None else item.get("homekit", {}).get("configured_by_filter")
        actual = "included" if observed is True else "excluded" if observed is False else "unknown"
        if actual == "unknown":
            status = "unknown"
            unknown += 1
        elif actual == wanted:
            status = "satisfied"
            satisfied += 1
        else:
            status = "open"
            open_count += 1
        results.append({"entity_id": entity_id, "desired": wanted, "observed": actual, "status": status})
    fingerprint_changed = bool(baseline_fingerprint and current_fingerprint and baseline_fingerprint != current_fingerprint)
    return {
        "entry_id": entry_id,
        "results": results,
        "summary": {"satisfied": satisfied, "open": open_count, "unknown": unknown, "fingerprint_changed": fingerprint_changed},
        "apple_home_visible": "unknown",
        "additional_external_changes": "unknown" if fingerprint_changed else "not_detected",
    }
