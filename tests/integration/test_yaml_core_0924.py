"""Actual Core YAML import/reload of an isolated HomeKit configuration."""
import pytest
from homeassistant import config_entries
from homeassistant.config import async_hass_config_yaml
from homeassistant.const import __version__
from homeassistant.setup import async_setup_component

from custom_components.homekit_manager.yaml_adapter import (
    YamlAdapterBlocked,
    YamlHomeKitAdapter,
)


async def test_isolated_yaml_file_apply_is_imported_by_core(hass, tmp_path, monkeypatch):
    async def no_network_start(_self):
        return None

    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    (tmp_path / "configuration.yaml").write_text("homekit: !include bridges.yaml\n")
    source = tmp_path / "bridges.yaml"
    source.write_text(
        "- name: Isolated YAML Bridge\n"
        "  port: 21079\n"
        "  filter:\n"
        "    include_entities:\n"
        "    - light.before\n"
    )
    config = await async_hass_config_yaml(hass)
    assert await async_setup_component(hass, "homekit", config)
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries("homekit")
    assert len(entries) == 1
    entry = entries[0]
    assert entry.source == "import"
    assert entry.options["filter"]["include_entities"] == ["light.before"]

    adapter = YamlHomeKitAdapter(tmp_path)
    plan = adapter.plan_filter(entry, {"include_entities": ["light.before", "light.after"]})
    before = source.read_bytes()
    if __version__ != "2026.10.4":
        with pytest.raises(YamlAdapterBlocked, match="Core-Version"):
            await adapter.async_apply_with_core(hass, entry, plan, isolated_authority=True)
        assert source.read_bytes() == before
        return
    result = await adapter.async_apply_with_core(hass, entry, plan, isolated_authority=True)
    assert result.state == "verified_core"
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.options["filter"]["include_entities"] == ["light.before", "light.after"]
    assert updated.entry_id == entry.entry_id
    assert updated.state.value == "loaded"

    # In this Core version the reload service also reloads native entries.
    # A mixed installation must be blocked before changing the YAML file.
    before = source.read_bytes()
    native = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="Native Neighbor",
        data={"name": "Native Neighbor", "port": 21081}, options={"mode": "bridge", "filter": {}},
        source=config_entries.SOURCE_USER, entry_id="native-neighbor", unique_id=None,
        discovery_keys={}, subentries_data=None,
    )
    await hass.config_entries.async_add(native)
    await hass.async_block_till_done()
    next_plan = adapter.plan_filter(updated, {"include_entities": ["light.before"]})
    with pytest.raises(YamlAdapterBlocked, match="native HomeKit"):
        await adapter.async_apply_with_core(hass, updated, next_plan, isolated_authority=True)
    assert source.read_bytes() == before


async def test_direct_configuration_yaml_apply_is_imported_by_core(hass, tmp_path, monkeypatch):
    async def no_network_start(_self):
        return None

    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    source = tmp_path / "configuration.yaml"
    before = (
        b"# outside comment retained\n"
        b"homekit:\n"
        b"  - name: Direct YAML Bridge\n"
        b"    port: 21089\n"
        b"    filter:\n"
        b"      include_entities:\n"
        b"        - light.before\n"
        b"logger:\n"
        b"  default: warning\n"
    )
    source.write_bytes(before)
    config = await async_hass_config_yaml(hass)
    assert await async_setup_component(hass, "homekit", config)
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries("homekit")
    assert len(entries) == 1
    entry = entries[0]
    assert entry.source == config_entries.SOURCE_IMPORT
    original_id = entry.entry_id
    adapter = YamlHomeKitAdapter(tmp_path)
    plan = adapter.plan_filter(entry, {"include_entities": ["light.before", "light.after"]})
    if __version__ != "2026.10.4":
        with pytest.raises(YamlAdapterBlocked, match="Core-Version"):
            await adapter.async_apply_with_core(hass, entry, plan, isolated_authority=True)
        assert source.read_bytes() == before
        return
    result = await adapter.async_apply_with_core(hass, entry, plan, isolated_authority=True)
    assert result.state == "verified_core"
    assert result.backup_path.read_bytes() == before
    assert source.read_bytes().startswith(b"# outside comment retained\n")
    assert source.read_bytes().endswith(b"logger:\n  default: warning\n")
    updated = hass.config_entries.async_get_entry(original_id)
    assert updated.entry_id == original_id and updated.source == config_entries.SOURCE_IMPORT
    assert updated.state.value == "loaded"
    assert updated.options["filter"]["include_entities"] == ["light.before", "light.after"]
