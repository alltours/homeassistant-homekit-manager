"""The actual Core 2026.10.4 config-entry lifecycle, with HAP network off."""
import pytest
from types import SimpleNamespace
from homeassistant import config_entries

from custom_components.homekit_manager.homekit_writer import HomeKitWriter, OptionsDiff, HomeKitWriteBlocked, HomeKitWriteDisabled
from custom_components.homekit_manager.native_adapter import NativeHomeKitAdapter


async def test_direct_native_writer_refuses_accessory_mode_before_mutation():
    entry = SimpleNamespace(entry_id="camera-entry", domain="homekit", source="user",
                            data={"name": "Camera"}, options={"mode": "accessory", "filter": {}})
    class Entries:
        def async_get_entry(self, _entry_id):
            return entry

        def async_update_entry(self, *_args, **_kwargs):
            raise AssertionError("Accessory entry must never be mutated")

    hass = SimpleNamespace(config_entries=Entries())
    diff = OptionsDiff("camera-entry", {"filter": {}}, {"filter": {"include_entities": ["camera.front"]}},
                       ("filter",), ("camera.front",), {"summary": {"blocked": False}})
    with pytest.raises(HomeKitWriteBlocked, match="Bridge-Modus"):
        await HomeKitWriter(hass, test_environment=True, apply_enabled=True).async_apply(diff)


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
        {"entity_id": "light.before", "homekit": {"configured_by_filter": True}, "compatibility": {"status": "supported"}, "registry_entry_present": True, "state_present": True},
        {"entity_id": "light.after", "homekit": {"configured_by_filter": False}, "compatibility": {"status": "supported"}, "registry_entry_present": True, "state_present": True},
    ]
    plan = adapter.plan_filter(bridge, document, inventory)
    assert adapter.reconcile(plan) == "not_applied"
    result = await adapter.apply(plan)
    assert result["verification"] == "verified_options"
    assert adapter.reconcile(plan) == "verified_options"
    reopened = NativeHomeKitAdapter(hass, isolated_test_authority=True)
    assert await reopened.reconcile_operation(plan.operation_id) == "verified_options"
    with pytest.raises(HomeKitWriteBlocked, match="Operation-ID"):
        await reopened.apply(plan)
    assert await adapter.recover(plan) == "verified_options_restore"
    assert adapter.reconcile(plan) == "not_applied"
    assert await reopened.reconcile_operation(plan.operation_id) == "not_applied"


async def test_native_writer_rejects_unproven_fields_and_invalid_filters_before_core_update(hass, monkeypatch):
    async def no_network_start(_self):
        return None

    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    entry = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="Native Schema Gate",
        data={"name": "Native Schema Gate", "port": 21098},
        options={"mode": "bridge", "filter": {"include_entities": ["light.before"]}},
        source=config_entries.SOURCE_USER, entry_id="native-schema-gate", unique_id=None,
        discovery_keys={}, subentries_data=None,
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    before = dict(entry.options)
    writer = HomeKitWriter(hass, test_environment=True, apply_enabled=True)
    bad_diffs = (
        OptionsDiff(entry.entry_id, {"entity_config": {}}, {"entity_config": {"light.before": {"name": "Changed"}}},
                    ("entity_config",), (), {}),
        OptionsDiff(entry.entry_id, {"filter": before["filter"]}, {"filter": {"future_rule": ["light.after"]}},
                    ("filter",), (), {}),
        OptionsDiff(entry.entry_id, {"filter": before["filter"]}, {"filter": {"include_entities": ["not_an_entity_id"]}},
                    ("filter",), (), {}),
    )
    for diff in bad_diffs:
        with pytest.raises(HomeKitWriteBlocked):
            await writer.async_apply(diff)
        assert dict(entry.options) == before
