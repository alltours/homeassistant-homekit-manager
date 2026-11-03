"""Decision drafts and non-mutating plans for taking over an existing bridge.

This module deliberately has no writer, grant, reload or config-entry access.
It only validates a manager-owned decision draft against an already built
coordinator snapshot and calculates a deterministic, hypothetical plan.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from homeassistant.helpers.storage import Store

DECISION_SCHEMA_VERSION = 1
DECISIONS = frozenset({"KEEP", "REMOVE", "REVIEW"})
TOMBSTONE_DECISIONS = frozenset({"KEEP_TOMBSTONE", "ARCHIVE_TOMBSTONE", "REMOVE_DECISION", "REVIEW"})
STALE_INCLUDE_DECISIONS = frozenset({"KEEP_STALE_INCLUDE", "REMOVE_STALE_INCLUDE", "REPLACE_WITH_VERIFIED_SUCCESSOR", "REVIEW"})
_MAX_HISTORY = 50


class SelectionDraftError(ValueError):
    """A draft cannot be safely validated against the current snapshot."""


class SelectionDraftConflict(SelectionDraftError):
    """The snapshot changed since the draft was created."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(UTC).isoformat()


def empty_draft(entry_id: str, revision: int, snapshot_fingerprint: str, timestamp: str | None = None) -> dict[str, Any]:
    """Return an empty draft; current entities are intentionally not auto-KEEP."""
    stamp = timestamp or now()
    return {
        "schema_version": DECISION_SCHEMA_VERSION,
        "bridge_entry_id": entry_id,
        "created_at": stamp,
        "updated_at": stamp,
        "snapshot_revision": revision,
        "snapshot_fingerprint": snapshot_fingerprint,
        "decisions": {},
        "tombstones": {},
        "stale_includes": {},
        "history": [],
    }


def _choice(value: Any, allowed: frozenset[str], field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise SelectionDraftError(f"Ungültige Entscheidung für {field}: {value!r}")
    return value


def _entry(value: Any, allowed: frozenset[str], *, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SelectionDraftError("Entscheidungseinträge müssen Objekte sein")
    decision = _choice(value.get("decision"), allowed, "Entscheidung")
    entry = {
        "decision": decision,
        "decision_source": value.get("decision_source", "user"),
        "confirmation_status": value.get("confirmation_status", "confirmed"),
        "identity": dict(value.get("identity") or {}),
        "updated_at": value.get("updated_at") or now(),
    }
    if entry["decision_source"] not in {"user", "system_default_review"}:
        raise SelectionDraftError("Unbekannte Entscheidungsquelle")
    if entry["confirmation_status"] not in {"pending", "confirmed"}:
        raise SelectionDraftError("Unbekannter Bestätigungsstatus")
    if allowed is TOMBSTONE_DECISIONS:
        entry["state"] = {
            "KEEP_TOMBSTONE": "HISTORICAL_DECISION",
            "ARCHIVE_TOMBSTONE": "ARCHIVED_TOMBSTONE",
            "REMOVE_DECISION": "EXPLICITLY_REMOVED",
            "REVIEW": "ORPHANED_DECISION",
        }[decision]
    else:
        entry["state"] = "ACTIVE_DECISION" if allowed is DECISIONS else "REVIEW_REQUIRED"
    validation = value.get("technical_validation", {"status": "not_verified"})
    if not isinstance(validation, dict):
        raise SelectionDraftError("technical_validation muss ein Objekt sein")
    entry["technical_validation"] = dict(validation)
    if identity is not None and entry["identity"] and dict(entry["identity"]) != dict(identity):
        raise SelectionDraftConflict("Identitätsmerkmale der Entität haben sich verändert")
    return entry


def normalize_draft(raw: Any, *, entry_id: str, revision: int, snapshot_fingerprint: str, identities: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Validate and normalize a user draft without assigning implicit choices."""
    if raw is None:
        return empty_draft(entry_id, revision, snapshot_fingerprint)
    if not isinstance(raw, dict):
        raise SelectionDraftError("Entscheidungsentwurf muss ein Objekt sein")
    if raw.get("schema_version") != DECISION_SCHEMA_VERSION:
        raise SelectionDraftError(f"Unbekannte Entscheidungs-Schema-Version: {raw.get('schema_version')!r}")
    if raw.get("bridge_entry_id") != entry_id:
        raise SelectionDraftConflict("Entwurf gehört zu einer anderen HomeKit-Bridge")
    if raw.get("snapshot_revision") != revision or raw.get("snapshot_fingerprint") != snapshot_fingerprint:
        raise SelectionDraftConflict("Der Entwurf basiert auf einem veralteten Snapshot")
    identities = identities or {}
    normalized = empty_draft(entry_id, revision, snapshot_fingerprint, raw.get("created_at") if isinstance(raw.get("created_at"), str) else None)
    normalized["updated_at"] = raw.get("updated_at") if isinstance(raw.get("updated_at"), str) else now()
    for field, allowed in (("decisions", DECISIONS), ("tombstones", TOMBSTONE_DECISIONS), ("stale_includes", STALE_INCLUDE_DECISIONS)):
        values = raw.get(field, {})
        if not isinstance(values, dict):
            raise SelectionDraftError(f"{field} muss ein Objekt sein")
        for entity_id, value in values.items():
            if not isinstance(entity_id, str) or "." not in entity_id:
                raise SelectionDraftError(f"Ungültige Entity-ID in {field}")
            normalized[field][entity_id] = _entry(value, allowed, identity=identities.get(entity_id))
    history = raw.get("history", [])
    if not isinstance(history, list):
        raise SelectionDraftError("history muss eine Liste sein")
    normalized["history"] = [item for item in history[-_MAX_HISTORY:] if isinstance(item, dict)]
    return normalized


def _identity(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in ("entity_id", "unique_id", "device_id", "integration_domain", "config_entry_id")
        if item.get(key) is not None
    }


def snapshot_from_coordinator(coordinator: Any) -> dict[str, Any]:
    """Build a redaction-safe snapshot view from the coordinator's atomic read model."""
    bridge = coordinator.selected_bridge()
    entry_id = bridge.get("entry_id") if bridge else None
    inventory = [deepcopy(item) for item in coordinator.inventory]
    inventory_by_id = {item.get("entity_id"): item for item in inventory if item.get("entity_id")}
    runtime = coordinator.runtime_diagnosis or {}
    current_ids = sorted({
        entity_id for entity_id, item in inventory_by_id.items()
        if item.get("homekit", {}).get("current_status") == "included"
        or runtime.get("entity_status", {}).get(entity_id) == "published_verified"
    })
    runtime_ids = sorted(entity_id for entity_id, status in runtime.get("entity_status", {}).items() if status == "published_verified")
    native_includes = sorted((bridge or {}).get("filter", {}).get("include_entities", []) or [])
    stale_includes = sorted(set(native_includes) - set(inventory_by_id))
    manager_doc = getattr(getattr(coordinator, "yaml_snapshot", None), "document", {}) or {}
    saved = manager_doc.get("bridges", {}).get(entry_id, {}) if entry_id else {}
    historical_ids = sorted(entity_id for entity_id in (saved.get("entities", {}) or {}) if entity_id not in inventory_by_id)
    rows = []
    for entity_id in current_ids:
        item = inventory_by_id[entity_id]
        rows.append({
            "entity_id": entity_id,
            "name": item.get("name") or entity_id,
            "domain": item.get("domain"),
            "device_name": item.get("device_name"),
            "area_name": item.get("area_name"),
            "integration_domain": item.get("integration_domain"),
            "native_selected": item.get("homekit", {}).get("configured_by_filter") is True,
            "runtime_publication": runtime.get("entity_status", {}).get(entity_id, item.get("homekit", {}).get("runtime_publication", "unknown")),
            "availability": item.get("availability_status", "unknown"),
            "manager_decision": (saved.get("entities", {}) or {}).get(entity_id),
            "identity": _identity(item),
        })
    return {
        "bridge_entry_id": entry_id,
        "bridge_title": (bridge or {}).get("title"),
        "snapshot_revision": getattr(coordinator, "snapshot_revision", 0),
        "snapshot_fingerprint": getattr(coordinator, "fingerprint", None),
        "snapshot_timestamp": getattr(coordinator, "snapshot_timestamp", None),
        "snapshot_complete": bool(getattr(coordinator, "snapshot_complete", False)),
        "reconciliation_state": (coordinator.selection_reconciliation or {}).get("state", "unknown"),
        "selection_conflict": bool((coordinator.selection_reconciliation or {}).get("selection_conflict", False)),
        "metadata_unresolved": (coordinator.selection_reconciliation or {}).get("state") == "mismatch",
        "migration_blocked": True,
        "write_enabled": False,
        "native_filter": deepcopy((bridge or {}).get("filter") or {}),
        "current_entity_ids": current_ids,
        "runtime_entity_ids": runtime_ids,
        "current_entities": rows,
        "stale_manager_decisions": [{"entity_id": entity_id, "decision": (saved.get("entities", {}) or {}).get(entity_id, "exclude"), "identity": {}} for entity_id in historical_ids],
        "stale_native_includes": [{"entity_id": entity_id} for entity_id in stale_includes],
        "runtime_completeness": runtime.get("completeness", "unknown"),
        "ambiguous_runtime_count": runtime.get("ambiguous_accessory_count", 0),
    }


def build_plan(snapshot: Mapping[str, Any], raw_draft: Any) -> dict[str, Any]:
    """Calculate a deterministic plan; never calls a Home Assistant mutator."""
    entry_id = snapshot.get("bridge_entry_id")
    current_ids = set(snapshot.get("current_entity_ids") or [])
    runtime_ids = set(snapshot.get("runtime_entity_ids") or [])
    identities = {row["entity_id"]: row.get("identity", {}) for row in snapshot.get("current_entities", [])}
    draft = normalize_draft(raw_draft, entry_id=entry_id, revision=snapshot.get("snapshot_revision"), snapshot_fingerprint=snapshot.get("snapshot_fingerprint"), identities=identities)
    decisions = draft["decisions"]
    tombstones = draft["tombstones"]
    stale = draft["stale_includes"]
    stale_manager_ids = {item["entity_id"] for item in snapshot.get("stale_manager_decisions", [])}
    stale_include_ids = {item["entity_id"] for item in snapshot.get("stale_native_includes", [])}
    unknown_decisions = sorted(set(decisions) - current_ids)
    unknown_tombstones = sorted(set(tombstones) - stale_manager_ids)
    unknown_stale = sorted(set(stale) - stale_include_ids)
    if unknown_decisions:
        raise SelectionDraftError("Entscheidung gehört nicht zu einer aktuellen Entität: " + ", ".join(unknown_decisions))
    if unknown_tombstones:
        raise SelectionDraftError("Unbekannter historischer Tombstone: " + ", ".join(unknown_tombstones))
    if unknown_stale:
        raise SelectionDraftError("Unbekannte stale native Referenz: " + ", ".join(unknown_stale))
    reviewed = {entity_id: decisions.get(entity_id, {}).get("decision", "REVIEW") for entity_id in sorted(current_ids)}
    keep_ids = {entity_id for entity_id, decision in reviewed.items() if decision == "KEEP"}
    remove_ids = {entity_id for entity_id, decision in reviewed.items() if decision == "REMOVE"}
    open_entities = sorted(entity_id for entity_id, decision in reviewed.items() if decision == "REVIEW")
    open_tombstones = sorted(entity_id for entity_id in stale_manager_ids if tombstones.get(entity_id, {}).get("decision", "REVIEW") == "REVIEW")
    open_stale = sorted(entity_id for entity_id in stale_include_ids if stale.get(entity_id, {}).get("decision", "REVIEW") == "REVIEW")
    replacement_blockers = sorted(entity_id for entity_id in stale_include_ids if stale.get(entity_id, {}).get("decision") == "REPLACE_WITH_VERIFIED_SUCCESSOR")
    target_ids = sorted(keep_ids)
    new_publications = sorted(keep_ids - runtime_ids)
    accessory_removals = sorted(runtime_ids - keep_ids)
    stale_to_remove = sorted(entity_id for entity_id in stale_include_ids if stale.get(entity_id, {}).get("decision") == "REMOVE_STALE_INCLUDE")
    blockers = []
    if not snapshot.get("bridge_entry_id"):
        blockers.append("Keine eindeutig ausgewählte HomeKit-Bridge")
    if not snapshot.get("snapshot_complete"):
        blockers.append("Snapshot unvollständig")
    if snapshot.get("selection_conflict"):
        blockers.append("Echter Auswahlkonflikt")
    if snapshot.get("ambiguous_runtime_count", 0):
        blockers.append("Runtime-Zuordnung nicht eindeutig")
    if snapshot.get("runtime_completeness") not in {"complete", "verified"}:
        blockers.append("HAP-Runtime-Evidenz unvollständig")
    if open_entities:
        blockers.append("Offene Entscheidungen für aktuelle Entitäten")
    if open_tombstones:
        blockers.append("Offene historische Tombstones")
    if open_stale:
        blockers.append("Offene stale native Includes")
    if replacement_blockers:
        blockers.append("Nachfolger technisch nicht verifiziert")
    if snapshot.get("metadata_unresolved"):
        blockers.append("Historische Metadaten ungeklärt")
    def stable_entries(values: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
        return {
            entity_id: {
                "decision": item.get("decision"),
                "decision_source": item.get("decision_source"),
                "confirmation_status": item.get("confirmation_status"),
                "identity": item.get("identity", {}),
            }
            for entity_id, item in sorted(values.items())
        }

    plan_input = {
        "bridge_entry_id": entry_id,
        "snapshot_revision": snapshot.get("snapshot_revision"),
        "snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
        "current_entity_ids": sorted(current_ids),
        "runtime_entity_ids": sorted(runtime_ids),
        "decisions": stable_entries(decisions),
        "tombstones": stable_entries(tombstones),
        "stale_includes": stable_entries(stale),
        "target_entity_ids": target_ids,
    }
    plan_fingerprint = fingerprint(plan_input)
    return {
        "schema_version": DECISION_SCHEMA_VERSION,
        "bridge_entry_id": entry_id,
        "snapshot_revision": snapshot.get("snapshot_revision"),
        "snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
        "plan_fingerprint": plan_fingerprint,
        "counts": {"keep": len(keep_ids), "remove": len(remove_ids), "review": len(open_entities), "tombstones": len(stale_manager_ids), "stale_includes": len(stale_include_ids)},
        "current_native_includes": sorted(snapshot.get("native_filter", {}).get("include_entities", []) or []),
        "hypothetical_target_includes": target_ids,
        "new_publications": new_publications,
        "accessory_removals": accessory_removals,
        "stale_includes_to_remove": stale_to_remove,
        "tombstones_handled": sorted(entity_id for entity_id in stale_manager_ids if tombstones.get(entity_id, {}).get("decision", "REVIEW") != "REVIEW"),
        "open_decisions": {"entities": open_entities, "tombstones": open_tombstones, "stale_includes": open_stale},
        "blockers": blockers,
        "decision_complete": not blockers,
        "migration_ready": False,
        "apply_allowed": False,
        "write_grant_issued": False,
        "native_mutation_performed": False,
        "message": "Nicht mutierende Vorschau. Die produktive HomeKit-Konfiguration bleibt unverändert.",
    }


def public_view(snapshot: Mapping[str, Any], raw_draft: Any) -> dict[str, Any]:
    """Return the UI/API view with explicit REVIEW defaults but no persisted guesses."""
    stale_error = None
    try:
        draft = normalize_draft(raw_draft, entry_id=snapshot.get("bridge_entry_id"), revision=snapshot.get("snapshot_revision"), snapshot_fingerprint=snapshot.get("snapshot_fingerprint"))
    except SelectionDraftConflict as err:
        # A stale draft remains visible for auditability, but is never treated
        # as current and cannot produce a plan until the user reloads it.
        stale_error = str(err)
        draft = dict(raw_draft) if isinstance(raw_draft, dict) else empty_draft(
            snapshot.get("bridge_entry_id"), snapshot.get("snapshot_revision"), snapshot.get("snapshot_fingerprint")
        )
        for section in ("decisions", "tombstones", "stale_includes"):
            if not isinstance(draft.get(section), dict):
                draft[section] = {}
    except SelectionDraftError as err:
        stale_error = str(err)
        draft = empty_draft(snapshot.get("bridge_entry_id"), snapshot.get("snapshot_revision"), snapshot.get("snapshot_fingerprint"))
    plan = None
    plan_error = stale_error
    if stale_error is None:
        try:
            plan = build_plan(snapshot, draft)
        except SelectionDraftError as err:
            plan_error = str(err)
    entities = []
    for item in snapshot.get("current_entities", []):
        decision = draft["decisions"].get(item["entity_id"], {}).get("decision", "REVIEW")
        entities.append(dict(item, user_decision=decision))
    tombstones = []
    for item in snapshot.get("stale_manager_decisions", []):
        decision = draft["tombstones"].get(item["entity_id"], {}).get("decision", "REVIEW")
        tombstones.append(dict(item, user_decision=decision))
    stale_includes = []
    for item in snapshot.get("stale_native_includes", []):
        decision = draft["stale_includes"].get(item["entity_id"], {}).get("decision", "REVIEW")
        stale_includes.append(dict(item, user_decision=decision))
    return {"schema_version": DECISION_SCHEMA_VERSION, "snapshot": dict(snapshot), "draft": draft, "entities": entities, "tombstones": tombstones, "stale_includes": stale_includes, "plan": plan, "plan_error": plan_error, "stale_draft": stale_error is not None}


class SelectionDraftStore:
    """HA Store for manager-only decisions; it never stores HAP secrets."""

    def __init__(self, hass) -> None:
        self._store = Store(hass, DECISION_SCHEMA_VERSION, "homekit_manager.selection_drafts")

    async def async_load(self) -> dict[str, dict[str, Any]]:
        data = await self._store.async_load()
        bridges = data.get("bridges", {}) if isinstance(data, dict) else {}
        return {str(key): value for key, value in bridges.items() if isinstance(key, str) and isinstance(value, dict)}

    async def async_save(self, bridge_id: str, draft: Mapping[str, Any]) -> None:
        current = await self.async_load()
        current[bridge_id] = deepcopy(dict(draft))
        await self._store.async_save({"schema_version": DECISION_SCHEMA_VERSION, "bridges": current})
