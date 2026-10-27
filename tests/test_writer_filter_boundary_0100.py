"""Prevent sparse inventories from hiding global HomeKit filter changes."""

import pytest

from custom_components.homekit_manager.filtering import evaluate_filter
from custom_components.homekit_manager.homekit_writer import (
    HomeKitWriteBlocked,
    build_options_diff,
)


def _diff(before, entity_id, desired):
    bridge = {"entry_id": "test", "data": {}, "options": {"filter": before}, "filter": before}
    inventory = [{"entity_id": entity_id, "available": True,
                  "compatibility": {"status": "supported"},
                  "homekit": {"configured_by_filter": evaluate_filter(entity_id, config=before).configured}}]
    document = {"schema_version": 1, "bridges": {"test": {
        "policy": "explicit_overrides", "entities": {entity_id: desired}}}}
    return build_options_diff(bridge, document, inventory)


@pytest.mark.parametrize("before, entity_id, desired", [
    ({"include_entities": ["light.only"]}, "light.only", "exclude"),
    ({"exclude_entities": ["light.blocked"]}, "light.blocked", "include"),
])
def test_blocks_default_flip_even_when_only_target_is_in_inventory(before, entity_id, desired):
    with pytest.raises(HomeKitWriteBlocked, match="Standardauswahl unbekannter Entitäten"):
        _diff(before, entity_id, desired)


def test_entity_exclude_is_safe_when_default_inclusion_remains():
    diff = _diff({}, "light.one", "exclude")
    assert diff.after["filter"]["exclude_entities"] == ["light.one"]
    assert evaluate_filter("light.future", config=diff.after["filter"]).configured is True


def test_explicit_include_can_override_excluded_domain_without_default_flip():
    diff = _diff({"exclude_domains": ["sensor"]}, "sensor.one", "include")
    assert evaluate_filter("sensor.other", config=diff.after["filter"]).configured is False
    assert evaluate_filter("switch.future", config=diff.after["filter"]).configured is True
