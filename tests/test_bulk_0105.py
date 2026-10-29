"""Regression for conservative, server-owned bulk selection."""

import pytest

from custom_components.homekit_manager.bulk import exclusion_reason, preview_bulk
from custom_components.homekit_manager.filtering import evaluate_filter
from custom_components.homekit_manager.change_planner import plan_changes


def entity(entity_id, **fields):
    return {
        "entity_id": entity_id, "device_id": "stairs", "device_registry_status": "main",
        "area_id": "hall", "device_area_id": "hall", "registry_entry_present": True,
        "state_present": True, "homekit": {"configured_by_filter": False},
        "compatibility": {"status": "supported"},
    } | fields


def test_disabled_diagnostics_and_unknown_are_never_bulk_eligible():
    inventory = [entity("binary_sensor.motion"), entity("sensor.battery", disabled_by="integration", entity_category="diagnostic"),
                 entity("sensor.signal", entity_category="diagnostic"), entity("sensor.other", compatibility={"status": "unknown"})]
    preview = preview_bulk(inventory, "device", "device:stairs")
    assert preview == {"total": 4, "eligible_entity_ids": ["binary_sensor.motion"],
                       "skipped": {"compatibility_unknown": 1, "diagnostic": 1, "disabled": 1},
                       "skipped_total": 3}


@pytest.mark.parametrize("fields,reason", [
    ({"hidden_by": "user"}, "hidden"), ({"device_disabled_by": "user"}, "disabled"),
    ({"entity_category": "diagnostic"}, "diagnostic"), ({"entity_category": "config"}, "config"),
    ({"registry_entry_present": False}, "registry_missing"), ({"state_present": False}, "no_state"),
    ({"compatibility": {"status": "conditionally_supported"}}, "conditional"),
    ({"compatibility": {"status": "unsupported"}}, "unsupported"),
    ({"device_registry_status": "missing"}, "device_missing"),
    ({"homekit": {"configured_by_filter": None}}, "filter_unknown"),
])
def test_all_exclusion_reasons(fields, reason):
    assert exclusion_reason(entity("light.test", **fields)) == reason


def test_area_uses_full_node_and_selection_rejects_unknown_entities():
    inventory = [entity("light.first"), entity("light.second", device_id=None, device_area_id=None, area_id="hall"),
                 entity("light.third", area_id="other", device_area_id="other")]
    assert preview_bulk(inventory, "area", "area:hall")["eligible_entity_ids"] == ["light.first", "light.second"]
    with pytest.raises(ValueError, match="unbekannte"):
        preview_bulk(inventory, "selection", "", entity_ids=["light.first", "light.missing"])


def test_filter_reason_has_one_value_in_both_wire_fields():
    result = evaluate_filter("light.first", config={"include_domains": ["light"]}).as_dict()
    assert result["reason"] == result["filter_reason"] == "domain_include"


@pytest.mark.parametrize("fields,reason", [
    ({"disabled_by": "integration"}, "disabled"),
    ({"hidden_by": "user"}, "hidden"),
    ({"entity_category": "diagnostic"}, "diagnostic"),
    ({"compatibility": {"status": "unknown"}}, "compatibility_unknown"),
    ({"state_present": False}, "no_state"),
])
def test_forged_include_is_blocked_at_apply_plan(fields, reason):
    item = entity("light.test", **fields)
    doc = {"schema_version": 1, "bridges": {"bridge": {"policy": "explicit_overrides", "entities": {"light.test": "include"}}}}
    plan = plan_changes({"entry_id": "bridge", "filter": {"include_entities": ["light.other"]}}, doc, [item])
    assert plan["summary"]["blocked"] and plan["changes"][0]["reason"] == reason
