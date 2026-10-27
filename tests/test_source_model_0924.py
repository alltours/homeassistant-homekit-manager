from types import SimpleNamespace
import pytest

from custom_components.homekit_manager.source_model import native_source, yaml_source


def entry(source):
    return SimpleNamespace(entry_id="b", source=source, data={"name": "Bridge", "port": 21064}, options={"mode": "bridge", "filter": {"include_entities": ["light.one"]}})


def test_native_model_is_immutable_and_source_bound():
    raw = entry("user")
    model = native_source(raw, "2026.10.4")
    assert model.capabilities.filter_write
    assert model.source == "user"
    with pytest.raises(TypeError):
        model.options["filter"] = {}
    with pytest.raises(TypeError):
        model.options["filter"]["include_entities"][0] = "light.changed"
    raw.options["filter"]["include_entities"].append("light.new")
    assert model.options["filter"]["include_entities"] == ("light.one",)
    assert native_source(raw, "2026.10.4").revision != model.revision


def test_yaml_model_requires_provenance_for_write_capability():
    imported = entry("import")
    assert not yaml_source(imported, "2026.10.4", provenance=None, file_revision=None).capabilities.filter_write
    assert yaml_source(imported, "2026.10.4", provenance="bridges.yaml:0", file_revision="abc").capabilities.filter_write
    assert not yaml_source(imported, "2026.11.0", provenance="bridges.yaml:0", file_revision="abc").capabilities.filter_write
    with pytest.raises(ValueError):
        yaml_source(entry("user"), "2026.10.4", provenance="bridges.yaml:0", file_revision="abc")
