"""Semantic value roundtrips; these tests make no HAP identity claim."""
from __future__ import annotations

from copy import deepcopy
import pytest

from custom_components.homekit_manager.conversion import ConversionBlocked, native_to_yaml, yaml_to_native


CORE = "2026.10.4"


@pytest.mark.parametrize("mode", ["bridge", "accessory"])
def test_repeated_roundtrip_preserves_supported_fields(mode):
    data = {"name": "Roundtrip Bridge", "port": 21072}
    options = {"mode": mode, "filter": {"include_entities": ["light.one"], "exclude_domains": ["sensor"]}, "entity_config": {"light.one": {"name": "Lamp"}}, "devices": []}
    initial = deepcopy(data | options)
    for _ in range(4):
        yaml_projection = native_to_yaml(data, options, core_version=CORE)
        native_projection = yaml_to_native(yaml_projection.yaml_bridge(), core_version=CORE)
        data, options = native_projection.data, native_projection.options
        assert data | options == initial
        assert not native_projection.identity_preserved
        assert not native_projection.pairing_preserved


def test_multiple_bridge_values_stay_separate():
    bridges = [
        {"name": "Bridge One", "port": 21073, "mode": "bridge", "filter": {"include_domains": ["light"]}},
        {"name": "Bridge Two", "port": 21074, "mode": "bridge", "filter": {"exclude_entities": ["sensor.one"]}},
    ]
    assert [native_to_yaml(yaml_to_native(item, core_version=CORE).data,
                           yaml_to_native(item, core_version=CORE).options,
                           core_version=CORE).yaml_bridge() for item in bridges] == bridges


@pytest.mark.parametrize("field", ["future_option", "index", "pairing_key"])
def test_unknown_top_level_field_is_blocked(field):
    with pytest.raises(ConversionBlocked):
        yaml_to_native({"name": "Bridge One", "port": 21073, field: "value"}, core_version=CORE)


def test_unknown_filter_field_and_misplaced_data_are_blocked():
    with pytest.raises(ConversionBlocked):
        yaml_to_native({"name": "Bridge One", "port": 21073, "filter": {"future": ["light.a"]}}, core_version=CORE)
    with pytest.raises(ConversionBlocked):
        native_to_yaml({"name": "Bridge One", "port": 21073}, {"name": "conflict"}, core_version=CORE)
    with pytest.raises(ConversionBlocked):
        native_to_yaml({"name": "Bridge One", "port": 21073}, {"future": "value"}, core_version=CORE)


def test_unverified_core_version_is_blocked():
    with pytest.raises(ConversionBlocked):
        yaml_to_native({"name": "Bridge One", "port": 21073}, core_version="2026.11.0")
