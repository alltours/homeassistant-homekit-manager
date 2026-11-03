"""Security and determinism tests for the 0.10.33 non-mutating takeover draft."""
from __future__ import annotations

import copy

import pytest

from custom_components.homekit_manager.selection_draft import (
    SelectionDraftConflict,
    SelectionDraftError,
    build_native_apply_document,
    build_plan,
    empty_draft,
    normalize_draft,
)


def snapshot() -> dict:
    current = [
        {
            "entity_id": f"light.room_{index}",
            "name": f"Room {index}",
            "identity": {"entity_id": f"light.room_{index}", "unique_id": f"uid-{index}", "device_id": f"device-{index}"},
            "homekit": {"configured_by_filter": True},
        }
        for index in range(23)
    ]
    return {
        "bridge_entry_id": "bridge-a",
        "snapshot_revision": 9,
        "snapshot_fingerprint": "snapshot-9",
        "snapshot_complete": True,
        "selection_conflict": False,
        "metadata_unresolved": False,
        "migration_blocked": True,
        "native_filter": {"include_entities": [item["entity_id"] for item in current] + ["binary_sensor.stale_1", "binary_sensor.stale_2"]},
        "current_entity_ids": [item["entity_id"] for item in current],
        "runtime_entity_ids": [item["entity_id"] for item in current],
        "current_entities": current,
        "stale_manager_decisions": [{"entity_id": f"sensor.old_{index}", "decision": "exclude"} for index in range(6)],
        "stale_native_includes": [{"entity_id": "binary_sensor.stale_1"}, {"entity_id": "binary_sensor.stale_2"}],
        "runtime_completeness": "complete",
        "ambiguous_runtime_count": 0,
    }


def complete_draft() -> dict:
    source = snapshot()
    draft = empty_draft("bridge-a", 9, "snapshot-9", "2026-11-03T00:00:00+00:00")
    draft["decisions"] = {
        entity_id: {"decision": "KEEP", "identity": row["identity"]}
        for entity_id, row in ((item["entity_id"], item) for item in source["current_entities"])
    }
    draft["tombstones"] = {
        item["entity_id"]: {"decision": "ARCHIVE_TOMBSTONE"}
        for item in source["stale_manager_decisions"]
    }
    draft["stale_includes"] = {
        item["entity_id"]: {"decision": "REMOVE_STALE_INCLUDE"}
        for item in source["stale_native_includes"]
    }
    return draft


def test_default_draft_never_assigns_keep():
    source = snapshot()
    plan = build_plan(source, None)
    assert plan["counts"] == {"keep": 0, "remove": 0, "review": 23, "tombstones": 6, "stale_includes": 2}
    assert plan["hypothetical_target_includes"] == []
    assert plan["apply_allowed"] is False
    assert plan["native_mutation_performed"] is False


def test_tombstone_decisions_have_explicit_auditable_states():
    draft = complete_draft()
    normalized = normalize_draft(draft, entry_id="bridge-a", revision=9, snapshot_fingerprint="snapshot-9")
    assert normalized["tombstones"]["sensor.old_0"]["state"] == "ARCHIVED_TOMBSTONE"
    draft["tombstones"]["sensor.old_0"]["decision"] = "REMOVE_DECISION"
    normalized = normalize_draft(draft, entry_id="bridge-a", revision=9, snapshot_fingerprint="snapshot-9")
    assert normalized["tombstones"]["sensor.old_0"]["state"] == "EXPLICITLY_REMOVED"


def test_complete_preservation_scenario_is_deterministic_and_still_not_applyable():
    source = snapshot()
    draft = complete_draft()
    first = build_plan(source, draft)
    second = build_plan(source, copy.deepcopy(draft))
    assert first["plan_fingerprint"] == second["plan_fingerprint"]
    assert first["counts"]["keep"] == 23
    assert first["counts"]["remove"] == 0
    assert first["counts"]["review"] == 0
    assert first["new_publications"] == []
    assert first["accessory_removals"] == []
    assert first["stale_includes_to_remove"] == ["binary_sensor.stale_1", "binary_sensor.stale_2"]
    assert len(first["tombstones_handled"]) == 6
    assert first["apply_allowed"] is False
    assert first["migration_ready"] is False


def test_missing_decisions_and_unresolved_history_block_plan():
    source = snapshot()
    draft = complete_draft()
    del draft["decisions"]["light.room_1"]
    del draft["tombstones"]["sensor.old_1"]
    plan = build_plan(source, draft)
    assert "Offene Entscheidungen für aktuelle Entitäten" in plan["blockers"]
    assert "Offene historische Tombstones" in plan["blockers"]


def test_bridge_and_snapshot_changes_fail_closed():
    source = snapshot()
    draft = complete_draft()
    wrong_bridge = dict(draft, bridge_entry_id="bridge-b")
    with pytest.raises(SelectionDraftConflict):
        normalize_draft(wrong_bridge, entry_id="bridge-a", revision=9, snapshot_fingerprint="snapshot-9")
    wrong_fingerprint = dict(draft, snapshot_revision=10, snapshot_fingerprint="changed")
    with pytest.raises(SelectionDraftConflict):
        build_plan(source, wrong_fingerprint)


def test_irrelevant_revision_change_is_allowed_only_with_same_semantic_fingerprint():
    source = snapshot()
    draft = complete_draft()
    draft["snapshot_revision"] = 8
    plan = build_plan(source, draft)
    assert plan["snapshot_revision"] == source["snapshot_revision"]
    assert plan["snapshot_fingerprint"] == source["snapshot_fingerprint"]


def test_unknown_entity_and_unverified_successor_are_blocked():
    source = snapshot()
    draft = complete_draft()
    draft["decisions"]["light.unknown"] = {"decision": "KEEP"}
    with pytest.raises(SelectionDraftError):
        build_plan(source, draft)
    draft = complete_draft()
    draft["stale_includes"]["binary_sensor.stale_1"] = {"decision": "REPLACE_WITH_VERIFIED_SUCCESSOR"}
    plan = build_plan(source, draft)
    assert "Nachfolger technisch nicht verifiziert" in plan["blockers"]


def test_reappeared_entity_identity_does_not_inherit_old_decision():
    source = snapshot()
    source["current_entity_ids"] = ["sensor.old_1"]
    source["runtime_entity_ids"] = []
    source["current_entities"] = [{"entity_id": "sensor.old_1", "identity": {"entity_id": "sensor.old_1", "unique_id": "new-identity"}}]
    draft = complete_draft()
    draft["decisions"] = {"sensor.old_1": {"decision": "KEEP", "identity": {"entity_id": "sensor.old_1", "unique_id": "old-identity"}}}
    with pytest.raises(SelectionDraftConflict):
        build_plan(source, draft)


def test_unexpected_fields_and_oversized_sections_fail_closed():
    draft = complete_draft()
    draft["unexpected"] = True
    with pytest.raises(SelectionDraftError):
        normalize_draft(draft, entry_id="bridge-a", revision=9, snapshot_fingerprint="snapshot-9")


def test_complete_draft_adapts_to_existing_native_operation_document_without_mutation():
    document, plan, synthetic = build_native_apply_document(snapshot(), complete_draft())
    bridge = document["bridges"]["bridge-a"]
    assert bridge["policy"] == "explicit_overrides"
    assert sum(status == "include" for status in bridge["entities"].values()) == 23
    assert bridge["entities"]["binary_sensor.stale_1"] == "exclude"
    assert bridge["entities"]["binary_sensor.stale_2"] == "exclude"
    assert len(synthetic) == 2
    assert plan["native_mutation_performed"] is False


def test_native_apply_adapter_requires_explicit_confirmed_identity():
    source = snapshot()
    draft = complete_draft()
    draft["decisions"]["light.room_0"]["confirmation_status"] = "pending"
    with pytest.raises(SelectionDraftError):
        build_native_apply_document(source, draft)

    draft = complete_draft()
    draft["decisions"]["light.room_0"]["identity"]["unique_id"] = "changed"
    with pytest.raises(SelectionDraftConflict):
        build_native_apply_document(source, draft)


def test_native_apply_adapter_rejects_stale_keep_and_broad_filters():
    source = snapshot()
    draft = complete_draft()
    draft["stale_includes"]["binary_sensor.stale_1"]["decision"] = "KEEP_STALE_INCLUDE"
    with pytest.raises(SelectionDraftError):
        build_native_apply_document(source, draft)

    source = snapshot()
    source["native_filter"]["include_domains"] = ["light"]
    with pytest.raises(SelectionDraftError):
        build_native_apply_document(source, complete_draft())

    draft = complete_draft()
    draft["history"] = [{"timestamp": "now", "event": "test", "unexpected": True}]
    with pytest.raises(SelectionDraftError):
        normalize_draft(draft, entry_id="bridge-a", revision=9, snapshot_fingerprint="snapshot-9")

    draft = empty_draft("bridge-a", 9, "snapshot-9")
    draft["decisions"] = {f"light.extra_{index}": {"decision": "REVIEW"} for index in range(2001)}
    with pytest.raises(SelectionDraftError):
        normalize_draft(draft, entry_id="bridge-a", revision=9, snapshot_fingerprint="snapshot-9")
