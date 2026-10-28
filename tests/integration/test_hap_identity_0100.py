"""Isolated Core/HAP storage exercise without network advertisement or pairing."""

from copy import deepcopy
from pathlib import Path

from homeassistant import config_entries

from custom_components.homekit_manager.homekit_writer import HomeKitWriter, OptionsDiff


async def test_filter_reload_keeps_isolated_hap_identity_and_allocations(hass, monkeypatch):
    from homeassistant.components.homekit import HomeKit
    from homeassistant.components.homekit.accessories import HomeDriver
    from homeassistant.components.homekit.util import get_persist_fullpath_for_entry_id

    async def no_network_start(_driver):
        return None

    async def no_network_stop(_driver):
        return None

    async def no_zeroconf(_hass):
        return None

    monkeypatch.setattr(HomeDriver, "async_start", no_network_start)
    monkeypatch.setattr(HomeDriver, "async_stop", no_network_stop)
    monkeypatch.setattr(HomeKit, "_async_show_setup_message", lambda _self: None)
    monkeypatch.setattr("homeassistant.components.homekit.zeroconf.async_get_async_instance", no_zeroconf)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    Path(hass.config.path(".storage")).mkdir(mode=0o700, exist_ok=True)
    hass.states.async_set("light.before", "on")
    hass.states.async_set("light.after", "off")
    await hass.async_block_till_done()
    entry = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="Isolated HAP Identity",
        data={"name": "Isolated HAP Identity", "port": 21097, "ip_address": "127.0.0.1", "advertise_ip": ["127.0.0.1"]},
        options={"mode": "bridge", "filter": {"include_entities": ["light.before"]}},
        source=config_entries.SOURCE_USER, entry_id="isolated-hap-identity", unique_id=None,
        discovery_keys={}, subentries_data=None,
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    assert entry.state.value == "loaded"
    first = entry.runtime_data.homekit
    assert first.driver is not None and first.bridge is not None
    first_mac = first.driver.state.mac
    first_aids = deepcopy(first.aid_storage.allocations)
    first_iids = deepcopy(first.iid_storage.allocations)
    assert "light.before" in first_aids and "light.after" not in first_aids
    assert first_iids
    assert Path(get_persist_fullpath_for_entry_id(hass, entry.entry_id)).is_file()

    diff = OptionsDiff(
        entry.entry_id,
        {"filter": {"include_entities": ["light.before"]}},
        {"filter": {"include_entities": ["light.before", "light.after"]}},
        ("filter",), ("light.after",), {"summary": {"blocked": False}},
    )
    await HomeKitWriter(hass, test_environment=True, apply_enabled=True).async_apply(diff)
    reloaded = hass.config_entries.async_get_entry(entry.entry_id)
    assert reloaded.state.value == "loaded"
    second = reloaded.runtime_data.homekit
    assert second is not first and second.driver is not None
    assert second.driver.state.mac == first_mac
    assert all(second.aid_storage.allocations.get(key) == value for key, value in first_aids.items())
    assert "light.after" in second.aid_storage.allocations
    assert all(second.iid_storage.allocations.get(aid) == values for aid, values in first_iids.items())
