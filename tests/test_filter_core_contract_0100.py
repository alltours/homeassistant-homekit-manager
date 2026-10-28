"""Compare the stand-alone preview with the installed Core 2026.10.4 filter."""

from itertools import product

from homeassistant.const import __version__ as CORE_VERSION
from homeassistant.helpers.entityfilter import FILTER_SCHEMA

from custom_components.homekit_manager.filtering import evaluate_filter


def test_all_six_filter_dimensions_against_core_and_homekit_registry_gate():
    assert CORE_VERSION == "2026.10.4"
    keys = (
        "include_entities", "exclude_entities", "include_domains",
        "exclude_domains", "include_entity_globs", "exclude_entity_globs",
    )
    values = (
        ["light.explicit"], ["light.excluded"], ["light"],
        ["sensor"], ["light.*_glob"], ["light.*_glob"],
    )
    entity_ids = (
        "light.explicit", "light.excluded", "light.other", "light.on_glob",
        "sensor.one", "switch.one",
    )
    for flags in product((False, True), repeat=len(keys)):
        config = {key: value for key, value, enabled in zip(keys, values, flags, strict=True) if enabled}
        core = FILTER_SCHEMA(config)
        for entity_id, category, hidden in product(entity_ids, (None, "diagnostic"), (None, "user")):
            selected = core.get_filter()(entity_id)
            expected = selected and (
                (category is None and hidden is None)
                or core.explicitly_included(entity_id)
            )
            actual = evaluate_filter(entity_id, category, hidden, config=config)
            assert actual.configured == selected, (config, entity_id, category, hidden, actual)
            assert actual.runtime_candidate == expected, (config, entity_id, category, hidden, actual)


def test_entity_include_plus_domain_exclude_preserves_core_default_include():
    config = {"include_entities": ["light.explicit"], "exclude_domains": ["sensor"]}
    assert evaluate_filter("switch.other", config=config).configured is True
    assert evaluate_filter("sensor.other", config=config).configured is False
    assert evaluate_filter("light.explicit", config=config).reason == "explicit_include"
    hidden = evaluate_filter("switch.other", hidden_by="user", config=config)
    assert hidden.configured is True
    assert hidden.runtime_candidate is False
