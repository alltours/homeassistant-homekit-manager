"""Run a real, isolated Home Assistant bootstrap around loopback HAP storage."""
from __future__ import annotations

import asyncio
import gc
import json
import os
from pathlib import Path
import socket
from unittest.mock import patch

from aiohomekit.controller.controller import Controller
from aiohomekit.controller.ip.discovery import IpDiscovery
from aiohomekit.controller.ip.pairing import IpPairing
from aiohomekit.zeroconf import HomeKitService
from homeassistant import config_entries
from homeassistant.bootstrap import async_setup_hass
from homeassistant.components.homekit import HomeKit
from homeassistant.components.homekit.util import (
    get_aid_storage_filename_for_entry_id,
    get_iid_storage_filename_for_entry_id,
    get_persist_fullpath_for_entry_id,
)
from homeassistant.runner import RuntimeConfig


ENTRY_ID = "isolated-hap-full-bootstrap"
ENTITY_ID = "input_boolean.restart_test"


class LocalAdvertiser:
    """Suppress LAN mDNS while leaving the real HAP TCP server running."""

    async def async_register_service(self, _service, **_kwargs):
        return None

    async def async_unregister_service(self, _service):
        return None

    async def async_update_service(self, _service):
        return None

    async def async_close(self):
        return None


async def local_advertiser(_hass):
    return LocalAdvertiser()


def free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]


async def run() -> None:
    shared = Path(os.environ["HKM_FULL_BOOTSTRAP_DIR"])
    phase = os.environ["HKM_FULL_BOOTSTRAP_PHASE"]
    if phase == "pair":
        (shared / "configuration.yaml").write_text(
            "homeassistant:\n  name: Isolated HAP Bootstrap\n"
            "input_boolean:\n  restart_test:\n    name: Restart Test\n"
            "logger:\n  default: critical\n"
        )
    with patch("homeassistant.components.homekit.zeroconf.async_get_async_instance", local_advertiser), patch.object(HomeKit, "_async_show_setup_message", lambda _self: None):
        hass = await async_setup_hass(RuntimeConfig(
            config_dir=str(shared), skip_pip=True,
            log_file=str(shared / "home-assistant.log"),
        ))
        assert hass is not None
        await hass.async_block_till_done()
        if phase == "pair":
            port = free_loopback_port()
            entry = config_entries.ConfigEntry(
                version=1, minor_version=1, domain="homekit", title="Full Bootstrap HAP",
                data={"name": "Full Bootstrap HAP", "port": port,
                      "ip_address": "127.0.0.1", "advertise_ip": ["127.0.0.1"]},
                options={"mode": "bridge", "filter": {"include_entities": [ENTITY_ID]}},
                source=config_entries.SOURCE_USER, entry_id=ENTRY_ID, unique_id=None,
                discovery_keys={}, subentries_data=None,
            )
            await hass.config_entries.async_add(entry)
            await hass.config_entries._store.async_save(hass.config_entries._data_to_save())
            assert (shared / ".storage" / "core.config_entries").is_file()
        else:
            entry = hass.config_entries.async_get_entry(ENTRY_ID)
            assert entry is not None and entry.source == config_entries.SOURCE_USER
            assert entry.options["filter"]["include_entities"] == [ENTITY_ID]
            if os.environ.get("HKM_EXPECT_BETA_EXCLUDES") == "1":
                assert entry.options["filter"]["exclude_entities"] == [
                    "sensor.blaue_tonne", "sensor.braune_tonne",
                    "sensor.gelbe_tonne", "sensor.graue_tonne",
                ]
            port = json.loads((shared / "public_identity.json").read_text())["port"]
            assert entry.data["port"] == port
        await hass.async_start()
        await hass.async_block_till_done()
        # Entity platforms are started by async_start.  Checking the state
        # before that lifecycle boundary is a transient bootstrap race on the
        # beta Core and does not prove that the configured runtime is ready.
        assert hass.states.get(ENTITY_ID) is not None
        assert entry.state.value == "loaded"
        homekit = entry.runtime_data.homekit
        assert homekit.status == 1
        aid = homekit.aid_storage.get_allocated_aid_for_entity_id(ENTITY_ID)
        assert aid is not None
        await homekit.aid_storage.async_save()
        await homekit.iid_storage.async_save()
        for path in (
            Path(get_persist_fullpath_for_entry_id(hass, ENTRY_ID)),
            Path(hass.config.path(".storage", get_aid_storage_filename_for_entry_id(ENTRY_ID))),
            Path(hass.config.path(".storage", get_iid_storage_filename_for_entry_id(ENTRY_ID))),
        ):
            assert path.is_file() and path.stat().st_size > 0
        controller = Controller()
        if phase == "pair":
            discovery = IpDiscovery(controller, HomeKitService.from_service_info(homekit.driver.mdns_service_info))
            try:
                finish = await asyncio.wait_for(discovery.async_start_pairing("isolated-full-bootstrap"), 10)
                pairing = await asyncio.wait_for(finish(homekit.driver.state.pincode.decode()), 10)
            finally:
                await discovery.close()
            await hass.async_add_executor_job(homekit.driver.persist)
        else:
            assert homekit.driver.state.paired
            pairing = IpPairing(controller, json.loads((shared / "controller_pairing.json").read_text()))
        accessories = await asyncio.wait_for(pairing.list_accessories_and_characteristics(), 10)
        accessory = next(item for item in accessories if item["aid"] == aid)
        iids = sorted(iid for service in accessory["services"]
                      for iid in [service["iid"], *(char["iid"] for char in service["characteristics"])])
        if phase == "pair":
            (shared / "public_identity.json").write_text(json.dumps({
                "port": port, "mac": homekit.driver.state.mac, "aid": aid, "iids": iids,
            }))
            secret = shared / "controller_pairing.json"
            secret.write_text(json.dumps(pairing.pairing_data))
            secret.chmod(0o600)
        else:
            before = json.loads((shared / "public_identity.json").read_text())
            assert homekit.driver.state.mac == before["mac"]
            assert aid == before["aid"] and iids == before["iids"]
        await pairing.shutdown()
        await hass.async_stop(force=True)


if __name__ == "__main__":
    asyncio.run(run())
    # Python 3.14.9/macOS intermittently crashes during interpreter-final GC
    # after even a minimal Core bootstrap with no Manager entry. Freezing GC
    # here affects only this already-stopped, short-lived test process.
    gc.freeze()
