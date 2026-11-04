"""Regression tests for the verified native filter Core-version boundary."""
from __future__ import annotations

from types import SimpleNamespace

from custom_components.homekit_manager.compatibility import classify_entity
from custom_components.homekit_manager.const import NATIVE_FILTER_WRITE_CORE_VERSIONS
from custom_components.homekit_manager.source_model import native_source


def _entry(source: str = "user") -> SimpleNamespace:
    return SimpleNamespace(
        entry_id="bridge-101",
        source=source,
        data={"name": "Bridge", "mode": "bridge"},
        options={"filter": {"include_entities": ["light.one"]}},
    )


def test_stable_2026_11_0_is_explicitly_verified_for_native_filter_writes():
    assert "2026.11.0" in NATIVE_FILTER_WRITE_CORE_VERSIONS
    assert native_source(_entry(), "2026.11.0").capabilities.filter_write is True


def test_unverified_core_versions_remain_read_only():
    assert native_source(_entry(), "2026.11.1").capabilities.filter_write is False
    assert native_source(_entry("import"), "2026.11.0").capabilities.filter_write is False


def test_stable_core_compatibility_projection_is_verified_without_opening_future_versions():
    entity = {"domain": "input_boolean", "attributes": {}}
    assert classify_entity(entity, core_version="2026.11.0").status == "supported"
    assert classify_entity(entity, core_version="2026.11.1").status == "unknown"
