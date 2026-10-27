"""The actual Core 2026.10.4 config-entry lifecycle, with HAP network off."""
import pytest
from homeassistant import config_entries

from custom_components.homekit_manager.homekit_writer import HomeKitWriter, OptionsDiff, HomeKitWriteDisabled
from custom_components.homekit_manager.native_adapter import NativeHomeKitAdapter


async def test_isolated_native_options_write_through_loaded_core_entry(hass, monkeypatch):
    async def no_network_start(_self):
        return None

    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    entry = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="Isolated Writer Bridge",
        data={"name": "Isolated Writer Bridge", "port": 21078},
        options={"mode": "bridge", "filter": {"include_entities": ["light.before"]}},
        source=config_entries.SOURCE_USER, entry_id="writer-isolated-core", unique_id=None,
        discovery_keys={}, subentries_data=None,
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    assert entry.state.value == "loaded"
    before_data = dict(entry.data)
    diff = OptionsDiff(
        entry.entry_id,
        {"filter": {"include_entities": ["light.before"]}},
        {"filter": {"include_entities": ["light.before", "light.after"]}},
        ("filter",), ("light.after",), {"summary": {"blocked": False}},
    )
    with pytest.raises(HomeKitWriteDisabled):
        await HomeKitWriter(hass).async_apply(diff)
    result = await HomeKitWriter(hass, test_environment=True, apply_enabled=True).async_apply(diff)
    assert result["applied"]
    reloaded = hass.config_entries.async_get_entry(entry.entry_id)
    assert reloaded.state.value == "loaded"
    assert dict(reloaded.data) == before_data
    assert reloaded.options["filter"] == {"include_entities": ["light.before", "light.after"]}


async def test_native_adapter_plans_and_recovers_on_loaded_core_entry(hass, monkeypatch):
    async def no_network_start(_self):
        return None
    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    entry = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="Isolated Adapter Bridge",
        data={"name": "Isolated Adapter Bridge", "port": 21080},
        options={"mode": "bridge", "filter": {"include_entities": ["light.before"]}},
        source=config_entries.SOURCE_USER, entry_id="native-adapter-isolated", unique_id=None,
        discovery_keys={}, subentries_data=None,
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    adapter = NativeHomeKitAdapter(hass, isolated_test_authority=True)
    bridge = {"entry_id": entry.entry_id, "source": "user", "filter": dict(entry.options["filter"])}
    document = {"schema_version": 1, "bridges": {entry.entry_id: {"policy": "explicit_overrides", "entities": {"light.after": "include"}}}}
    inventory = [
        {"entity_id": "light.before", "homekit": {"configured_by_filter": True}, "compatibility": {"status": "supported"}},
        {"entity_id": "light.after", "homekit": {"configured_by_filter": False}, "compatibility": {"status": "supported"}},
    ]
    plan = adapter.plan_filter(bridge, document, inventory)
    assert adapter.reconcile(plan) == "not_applied"
    assert (await adapter.apply(plan))["verification"] == "verified_options"
    assert adapter.reconcile(plan) == "verified_options"
    assert await adapter.recover(plan) == "verified_options_restore"
    assert adapter.reconcile(plan) == "not_applied"
