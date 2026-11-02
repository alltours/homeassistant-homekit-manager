"""0.10.31 mismatch semantics and positive-list planning tests."""
from __future__ import annotations

import json
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
    target = json.loads(
        (Path(__file__).parents[1] / "docs/reconciliation/homekit_manager_0.10.31_approved_selection.json").read_text(
            encoding="utf-8"
        )
    )["entity_ids"]
    stale = [
        "binary_sensor.flur_flur_haustur_sensor_haustur_1",
        "binary_sensor.flur_flur_haustur_sensor_haustur_2",
    ]
    stale_manager = [
        "input_select.anwesenheit_aktionsstatus",
        "sensor.anwesenheit_catarina_kindle",
        "sensor.anwesenheit_catarina_kindle_wifi",
        "sensor.anwesenheit_catarina_switch",
        "sensor.anwesenheit_catarina_switch_wifi",
        "sensor.robot_battery",
    ]
    snapshot = {
        "complete": True,
        "bridge": {
            "entry_id": "01KTHHYVPZ1T9804NQTJSCCXFJ",
            "port": 21064,
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
            "hap_baseline": {"mac": "1F:67:33:3C:6E:F7", "port": 21064},
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
