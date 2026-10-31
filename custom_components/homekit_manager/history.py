"""Redacted configuration history and restoration previews."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from .yaml_store import validate_document


def _safe_document(document: Mapping[str, Any]) -> dict[str, Any]:
    return validate_document(document)


def make_history_entry(document: Mapping[str, Any], *, reason: str = "draft_saved", fingerprint: str | None = None, bridge_id: str | None = None) -> dict[str, Any]:
    """Create a redacted history entry containing desired state only."""
    safe = _safe_document(document)
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "reason": reason,
        "document": safe,
        "fingerprint": fingerprint,
        "applied": False,
        "bridge_id": bridge_id,
    }


def compare_history(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Compare normalized bridge/entity desired states."""
    old = _safe_document(before)
    new = _safe_document(after)
    changes = []
    bridge_ids = sorted(set(old["bridges"]) | set(new["bridges"]))
    for bridge_id in bridge_ids:
        old_entities = old["bridges"].get(bridge_id, {}).get("entities", {})
        new_entities = new["bridges"].get(bridge_id, {}).get("entities", {})
        for entity_id in sorted(set(old_entities) | set(new_entities)):
            if old_entities.get(entity_id) == new_entities.get(entity_id):
                action = "unchanged"
            elif entity_id not in old_entities:
                action = "added"
            elif entity_id not in new_entities:
                action = "removed"
            else:
                action = "changed"
            changes.append({"bridge_id": bridge_id, "entity_id": entity_id, "action": action, "before": old_entities.get(entity_id), "after": new_entities.get(entity_id)})
    return {"changes": changes, "summary": {key: sum(item["action"] == key for item in changes) for key in ("added", "removed", "changed", "unchanged")}}


def restore_as_draft(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Return a validated copy suitable for a new draft, never as an active state."""
    return {"document": _safe_document(entry.get("document", {})), "restored": True, "applied": False}
