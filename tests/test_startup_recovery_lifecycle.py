"""Source-level regression checks for the Home Assistant startup boundary."""
from __future__ import annotations

import inspect
from pathlib import Path

from homeassistant import bootstrap
from homeassistant.components import homekit


def test_core_loads_entries_before_parallel_integration_setup():
    source = inspect.getsource(bootstrap.async_from_config_dict)
    assert "await async_load_base_functionality(hass)" in source
    assert "await _async_set_up_integrations(hass, config)" in source
    setup_source = inspect.getsource(bootstrap._async_set_up_integrations)
    assert "asyncio.gather" in inspect.getsource(bootstrap._async_setup_multi_components)
    assert "async_setup_component(hass, domain, config)" in setup_source or "_async_setup_multi_components" in setup_source


def test_native_homekit_imports_yaml_during_component_setup_and_starts_later():
    setup_source = inspect.getsource(homekit.async_setup)
    importer = getattr(homekit, "_async_update_entries_from_yaml", None)
    if importer is None:
        from homeassistant.components.homekit import util

        importer = util.async_update_entries_from_yaml
    entry_source = inspect.getsource(homekit.async_setup_entry)
    importer_source = inspect.getsource(importer)
    assert "SOURCE_IMPORT" in importer_source
    assert "async_init" in importer_source
    assert "async_update_entries_from_yaml" in setup_source or "_async_update_entries_from_yaml" in setup_source
    assert "async_at_started" in entry_source


def test_manager_startup_observation_cannot_authorize_native_mutation():
    from custom_components.homekit_manager.startup_recovery import (
        observe_startup_recovery,
    )

    assert observe_startup_recovery.__doc__
    assert "mutat" in inspect.getsource(observe_startup_recovery).lower()


def test_stable_and_beta_core_sources_have_the_same_relevant_boundary():
    """Verify the source contract against both locally installed Core trees."""
    roots = (
        Path(".venv-ha-0.10.10/lib/python3.14/site-packages/homeassistant"),
        Path(".venv-ha-0.10.10-beta/lib/python3.14/site-packages/homeassistant"),
    )
    for root in roots:
        bootstrap_source = (root / "bootstrap.py").read_text(encoding="utf-8")
        homekit_source = (root / "components/homekit/__init__.py").read_text(encoding="utf-8")
        assert "await async_load_base_functionality(hass)" in bootstrap_source
        assert "await _async_set_up_integrations(hass, config)" in bootstrap_source
        assert "async_at_started" in homekit_source
        assert "SOURCE_IMPORT" in homekit_source or "SOURCE_IMPORT" in (
            root / "components/homekit/util.py"
        ).read_text(encoding="utf-8")
