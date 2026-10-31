"""Worker invoked in two separate Python processes by the restart test.

All pairing material is kept in the caller's temporary directory and never
printed. The real HAP server listens on loopback only; mDNS is replaced.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import socket

from aiohomekit.controller.controller import Controller
from aiohomekit.controller.ip.discovery import IpDiscovery
from aiohomekit.controller.ip.pairing import IpPairing
from aiohomekit.zeroconf import HomeKitService
from homeassistant import config_entries
import pytest


class LocalAdvertiser:
    async def async_register_service(self, _service, **_kwargs):
        return None

    async def async_unregister_service(self, _service):
        return None

    async def async_update_service(self, _service):
        return None

    async def async_close(self):
        return None


@pytest.fixture
def hass_storage():
    return {}


async def test_worker(hass, monkeypatch, socket_enabled):
    from homeassistant.components.homekit import HomeKit
    from homeassistant.components.homekit.util import (
        get_aid_storage_filename_for_entry_id,
        get_iid_storage_filename_for_entry_id,
        get_persist_fullpath_for_entry_id,
    )

    shared = Path(os.environ["HKM_RESTART_DIR"])
    phase = os.environ["HKM_RESTART_PHASE"]
    hass.config.config_dir = str(shared)
    (shared / ".storage").mkdir(mode=0o700, exist_ok=True)
    # Core 2026.11 caches the ConfigEntryStore path at construction time.  The
    # HA test fixture creates it before this worker selects its isolated
    # directory, so recreate the manager before writing the pair phase.
    hass.config_entries = config_entries.ConfigEntries(hass, {"_": "isolated restart"})
    advertiser = LocalAdvertiser()

    async def local_advertiser(_hass):
        return advertiser

    monkeypatch.setattr("homeassistant.components.homekit.zeroconf.async_get_async_instance", local_advertiser)
    monkeypatch.setattr(HomeKit, "_async_show_setup_message", lambda _self: None)
    if phase == "pair":
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
    else:
        port = json.loads((shared / "public_identity.json").read_text())["port"]
    hass.states.async_set("light.restart", "on")
    await hass.async_block_till_done()
    if phase == "pair":
        entry = config_entries.ConfigEntry(
            version=1, minor_version=1, domain="homekit", title="Restart HAP",
            data={"name": "Restart HAP", "port": port, "ip_address": "127.0.0.1", "advertise_ip": ["127.0.0.1"]},
            options={"mode": "bridge", "filter": {"include_entities": ["light.restart"]}},
            source=config_entries.SOURCE_USER, entry_id="isolated-hap-process-restart", unique_id=None,
            discovery_keys={}, subentries_data=None,
        )
        await hass.config_entries.async_add(entry)
        await hass.config_entries._store.async_save(hass.config_entries._data_to_save())
        assert (shared / ".storage" / "core.config_entries").is_file()
    else:
        hass.config_entries = config_entries.ConfigEntries(hass, {"_": "isolated restart"})
        await hass.config_entries.async_initialize()
        entry = hass.config_entries.async_get_entry("isolated-hap-process-restart")
        assert entry is not None and entry.source == config_entries.SOURCE_USER
        assert entry.options["filter"]["include_entities"] == ["light.restart"]
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state.value == "loaded"
    homekit = entry.runtime_data.homekit
    aid = homekit.aid_storage.get_allocated_aid_for_entity_id("light.restart")
    assert aid is not None and homekit.status == 1
    await homekit.aid_storage.async_save()
    await homekit.iid_storage.async_save()
    assert Path(get_persist_fullpath_for_entry_id(hass, entry.entry_id)).is_file()
    assert Path(hass.config.path(".storage", get_aid_storage_filename_for_entry_id(entry.entry_id))).is_file()
    assert Path(hass.config.path(".storage", get_iid_storage_filename_for_entry_id(entry.entry_id))).is_file()

    controller = Controller()
    if phase == "pair":
        discovery = IpDiscovery(controller, HomeKitService.from_service_info(homekit.driver.mdns_service_info))
        try:
            finish = await asyncio.wait_for(discovery.async_start_pairing("isolated-restart"), 10)
            pairing = await asyncio.wait_for(finish(homekit.driver.state.pincode.decode()), 10)
        finally:
            await discovery.close()
        await hass.async_add_executor_job(homekit.driver.persist)
    else:
        assert homekit.driver.state.paired
        pairing = IpPairing(controller, json.loads((shared / "controller_pairing.json").read_text()))
    accessories = await asyncio.wait_for(pairing.list_accessories_and_characteristics(), 10)
    accessory = next(item for item in accessories if item["aid"] == aid)
    iids = sorted(
        iid for service in accessory["services"]
        for iid in [service["iid"], *(char["iid"] for char in service["characteristics"])]
    )
    if phase == "pair":
        (shared / "public_identity.json").write_text(json.dumps({"port": port, "mac": homekit.driver.state.mac,
                                                                  "aid": aid, "iids": iids}))
        secret = shared / "controller_pairing.json"
        secret.write_text(json.dumps(pairing.pairing_data))
        secret.chmod(0o600)
    else:
        before = json.loads((shared / "public_identity.json").read_text())
        assert homekit.driver.state.mac == before["mac"]
        assert aid == before["aid"] and iids == before["iids"]
    await pairing.shutdown()
    # Core 2026.11 keeps pyhap's connection-cleanup timer alive until the
    # HomeKit runtime is explicitly stopped.  Do this in the worker so the
    # two-process restart test verifies a clean lifecycle, not a leaked loop.
    await homekit.async_stop()
    await hass.async_block_till_done()
