"""Run Core's real HAP TCP server on loopback with mDNS kept local to the test."""

import asyncio
import socket
from pathlib import Path

from homeassistant import config_entries

from custom_components.homekit_manager.homekit_writer import HomeKitWriter, OptionsDiff


class LocalAdvertiser:
    def __init__(self):
        self.registered = 0
        self.unregistered = 0

    async def async_register_service(self, _service, **_kwargs):
        self.registered += 1

    async def async_unregister_service(self, _service):
        self.unregistered += 1

    async def async_close(self):
        return None


async def test_loopback_hap_server_survives_native_filter_reload(hass, monkeypatch, socket_enabled):
    from homeassistant.components.homekit import HomeKit
    from homeassistant.components.homekit.util import get_persist_fullpath_for_entry_id

    advertiser = LocalAdvertiser()

    async def local_advertiser(_hass):
        return advertiser

    monkeypatch.setattr("homeassistant.components.homekit.zeroconf.async_get_async_instance", local_advertiser)
    monkeypatch.setattr(HomeKit, "_async_show_setup_message", lambda _self: None)
    Path(hass.config.path(".storage")).mkdir(mode=0o700, exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    hass.states.async_set("light.before", "on")
    hass.states.async_set("light.after", "off")
    await hass.async_block_till_done()
    entry = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="Loopback HAP",
        data={"name": "Loopback HAP", "port": port, "ip_address": "127.0.0.1", "advertise_ip": ["127.0.0.1"]},
        options={"mode": "bridge", "filter": {"include_entities": ["light.before"]}},
        source=config_entries.SOURCE_USER, entry_id="isolated-hap-loopback", unique_id=None,
        discovery_keys={}, subentries_data=None,
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    assert entry.state.value == "loaded"
    first = entry.runtime_data.homekit
    assert first.driver is not None and first.status == 1
    assert advertiser.registered == 1
    mac = first.driver.state.mac
    before_aid = first.aid_storage.get_allocated_aid_for_entity_id("light.before")
    assert before_aid is not None
    assert Path(get_persist_fullpath_for_entry_id(hass, entry.entry_id)).is_file()

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /accessories HTTP/1.1\r\nHost: localhost\r\n\r\n")
    await writer.drain()
    response = await asyncio.wait_for(reader.read(128), 3)
    writer.close()
    await writer.wait_closed()
    assert response.startswith(b"HTTP/1.1")

    diff = OptionsDiff(
        entry.entry_id,
        {"filter": {"include_entities": ["light.before"]}},
        {"filter": {"include_entities": ["light.before", "light.after"]}},
        ("filter",), ("light.after",), {"summary": {"blocked": False}},
    )
    await HomeKitWriter(hass, test_environment=True, apply_enabled=True).async_apply(diff)
    second = hass.config_entries.async_get_entry(entry.entry_id).runtime_data.homekit
    assert second is not first and second.status == 1
    assert advertiser.registered == 2 and advertiser.unregistered == 1
    assert second.driver.state.mac == mac
    assert second.aid_storage.get_allocated_aid_for_entity_id("light.before") == before_aid
    assert second.aid_storage.get_allocated_aid_for_entity_id("light.after") is not None
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /accessories HTTP/1.1\r\nHost: localhost\r\n\r\n")
    await writer.drain()
    assert (await asyncio.wait_for(reader.read(128), 3)).startswith(b"HTTP/1.1")
    writer.close()
    await writer.wait_closed()
