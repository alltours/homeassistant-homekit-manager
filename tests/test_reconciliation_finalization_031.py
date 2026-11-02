"""0.10.31 mismatch semantics and positive-list planning tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

package = "custom_components.homekit_manager"
if package not in sys.modules:
    module = type(sys)(package)
    module.__path__ = [str(Path(__file__).parents[1] / "custom_components" / "homekit_manager")]
    sys.modules[package] = module

from custom_components.homekit_manager.positive_list_planning import build_positive_list_plan  # noqa: E402
from custom_components.homekit_manager.selection_reconciliation import reconcile_selection  # noqa: E402
from custom_components.homekit_manager.inventory_export import build_reconciliation_export  # noqa: E402


def entity(entity_id: str, *, reason: str = "explicit_include") -> dict:
    return {
        "entity_id": entity_id,
        "device_id": "device-1",
        "device_name": "Testgerät",
        "area_id": "area-1",
        "area_name": "Testbereich",
        "domain": entity_id.split(".", 1)[0],
        "homekit": {"configured_by_filter": True, "filter_reason": reason},
    }


def runtime(entity_ids: list[str]) -> dict:
    return {
        "state": "verified",
        "completeness": "verified",
        "entity_status": {entity_id: "published_verified" for entity_id in entity_ids},
        "accessories": [
            {"entity_id": entity_id, "aid": index + 1, "iid_signature": f"iid-{index}"}
            for index, entity_id in enumerate(entity_ids)
        ],
    }


def test_legacy_metadata_unresolved_is_not_a_native_set_conflict():
    present = ["light.one", "light.two"]
    result = reconcile_selection(
        {"bridges": {"bridge": {"policy": "explicit_overrides", "entities": {"sensor.gone": "exclude"}}}},
        "bridge",
        [entity(item) for item in present],
        {"include_entities": present},
        runtime(present),
    )

    assert result["state"] == "mismatch"
    assert result["diagnostic_state"] == "metadata_unresolved"
    assert result["selection_conflict"] is False
    assert result["differences"]["desired_not_native"] == []
    assert result["differences"]["native_not_desired"] == []
    assert result["migration_blocked"] is True
    assert {row["classification"] for row in result["deviations"]} == {
        "native_explicit_unmanaged", "stale_manager_decision",
    }


def test_positive_list_set_mismatch_remains_a_critical_conflict_candidate():
    result = reconcile_selection(
        {"bridges": {"bridge": {"policy": "positive_list", "entities": {"light.keep": "include"}}}},
        "bridge",
        [entity("light.keep"), entity("light.extra")],
        {"include_entities": ["light.keep", "light.extra"]},
        runtime(["light.keep", "light.extra"]),
    )

    assert result["diagnostic_state"] == "selection_conflict"
    assert result["selection_conflict"] is True
    assert result["differences"]["native_not_desired"] == ["light.extra"]


def test_export_preserves_conflict_classification_and_blocker_fields():
    alignment = reconcile_selection(
        {"bridges": {"bridge": {"policy": "explicit_overrides", "entities": {"sensor.gone": "exclude"}}}},
        "bridge",
        [entity("light.one")],
        {"include_entities": ["light.one"]},
        runtime(["light.one"]),
    )
    snapshot = build_reconciliation_export(
        {
            "integration_version": "0.10.31",
            "core_version": "2026.11.0b0",
            "snapshot_timestamp": "2026-11-02T12:00:00+00:00",
            "snapshot_revision": 1,
            "fingerprint": "test",
            "selected_bridge_id": "bridge",
            "snapshot_complete": True,
            "configuration_alignment": alignment,
        },
        [{"entry_id": "bridge", "filter": {"include_entities": ["light.one"]}}],
        {"findings": [], "summary": {}},
        runtime(["light.one"]),
    )
    assert snapshot["schema_version"] == 2
    assert snapshot["reconciliation"]["selection_conflict"] is False
    assert snapshot["reconciliation"]["diagnostic_state"] == "metadata_unresolved"
    assert snapshot["reconciliation"]["migration_blocked"] is True


def production_snapshot() -> tuple[list[str], dict]:
    # Use synthetic IDs in the public test suite.  Real installation-specific
    # targets are intentionally supplied from a local file outside the repo.
    target = [f"light.approved_{index:02d}" for index in range(23)]
    stale = [
        "binary_sensor.stale_filter_01",
        "binary_sensor.stale_filter_02",
    ]
    stale_manager = [
        "sensor.stale_manager_01",
        "sensor.stale_manager_02",
        "sensor.stale_manager_03",
        "sensor.stale_manager_04",
        "sensor.stale_manager_05",
        "sensor.stale_manager_06",
    ]
    snapshot = {
        "schema_version": 2,
        "complete": True,
        "bridge": {
            "entry_id": "bridge-1",
            "port": 21063,
            "filter": {"include_entities": target + stale},
        },
        "completeness": {
            "snapshot_complete": True,
            "reconciliation_rows_complete": True,
            "runtime_complete": True,
            "runtime_assignment_rows_complete": True,
        },
        "reconciliation": {
            "selection_conflict": False,
            "diagnostic_state": "metadata_unresolved",
            "migration_blocked": True,
            "differences": {"desired_not_native": [], "native_not_desired": [], "unknown_entities": [], "count": 6},
            "deviations": [
                {"entity_id": entity_id, "native_selection": None, "runtime_selection": "unknown", "severity": "critical", "classification": "stale_manager_decision"}
                for entity_id in stale_manager
            ],
        },
        "technical_findings": [
            {"code": "stale_filter_reference", "severity": "warning", "entity_id": entity_id}
            for entity_id in stale
        ],
        "runtime": {
            "completeness": "verified",
            "entity_status": {entity_id: "published_verified" for entity_id in target},
            "entity_assignments": [
                {"entity_id": entity_id, "aid": index + 1, "iid_signature": f"iid-{index}"}
                for index, entity_id in enumerate(target)
            ],
            "hap_baseline": {"mac": "AA:BB:CC:DD:EE:FF", "port": 21063},
        },
        "summary": {
            "selection_deviation_count": 6,
            "technical_finding_count": 2,
            "runtime_entity_assignment_count": 23,
        },
    }
    return target, snapshot


def test_production_shape_is_exactly_23_keep_with_no_publication_or_removal():
    target, snapshot = production_snapshot()
    plan = build_positive_list_plan(target, snapshot)

    assert plan["summary"]["keep"] == 23
    assert plan["summary"]["new_publications"] == 0
    assert plan["summary"]["desired_accessory_removals"] == 0
    assert plan["expected_new_publications"] == []
    assert plan["expected_removals"] == []
    assert len(plan["unchanged_entities"]) == 23
    assert all(row["status"] == "KEEP" for row in plan["entities"])
    # The count is safe, but stale critical manager decisions keep the later
    # write blocked until they are explicitly reviewed.
    assert plan["migration_ready"] is False
    assert any(row["code"] == "critical_reconciliation_deviation" for row in plan["blocking_reasons"])


@pytest.mark.parametrize(
    "target, expected_code",
    [([], "empty_target"), (["light.*"], "invalid_target_id"), (["light.one", "light.one"], "invalid_target_id")],
)
def test_unsafe_target_shapes_are_blocked(target, expected_code):
    _, snapshot = production_snapshot()
    plan = build_positive_list_plan(target, snapshot)
    assert any(row["code"] == expected_code for row in plan["blocking_reasons"])
    assert plan["migration_ready"] is False


def test_incomplete_snapshot_and_unknown_target_are_fail_closed():
    target, snapshot = production_snapshot()
    snapshot["complete"] = False
    snapshot["completeness"]["snapshot_complete"] = False
    target = target[:-1] + ["light.not_observed"]
    plan = build_positive_list_plan(target, snapshot)
    codes = {row["code"] for row in plan["blocking_reasons"]}
    assert "incomplete_snapshot" in codes
    assert "target_not_observed" in codes
    assert plan["migration_ready"] is False


def test_metadata_unresolved_blocks_even_without_critical_rows():
    target, snapshot = production_snapshot()
    snapshot["reconciliation"]["deviations"] = [
        {"entity_id": target[0], "native_selection": True, "runtime_selection": "published_verified", "severity": "warning", "classification": "native_explicit_unmanaged"},
    ]
    snapshot["reconciliation"]["migration_blocked"] = False
    snapshot["summary"]["selection_deviation_count"] = 1
    snapshot["technical_findings"] = []
    snapshot["summary"]["technical_finding_count"] = 0
    plan = build_positive_list_plan(target, snapshot)
    assert any(row["code"] == "unresolved_reconciliation_metadata" for row in plan["blocking_reasons"])
    assert plan["migration_ready"] is False


def test_historical_schema_is_accepted_as_evidence_but_never_as_migration_ready():
    target, snapshot = production_snapshot()
    snapshot["schema_version"] = 1
    plan = build_positive_list_plan(target, snapshot)
    assert any(row["code"] == "historical_schema" for row in plan["blocking_reasons"])
    assert plan["migration_ready"] is False


def test_inconsistent_counts_unknown_status_and_missing_hap_identity_block():
    target, snapshot = production_snapshot()
    snapshot["summary"]["runtime_entity_assignment_count"] = 999
    snapshot["runtime"]["entity_status"][target[0]] = "not_a_runtime_status"
    snapshot["runtime"]["entity_assignments"][0]["iid_signature"] = None
    plan = build_positive_list_plan(target, snapshot)
    codes = {row["code"] for row in plan["blocking_reasons"]}
    assert "runtime_count_mismatch" in codes
    assert "unknown_runtime_status" in codes
    assert "missing_hap_identity" in codes
