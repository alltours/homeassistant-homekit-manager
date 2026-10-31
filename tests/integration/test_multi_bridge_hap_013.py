"""Real two-bridge HAP coverage for the isolated migration engine."""
from __future__ import annotations

import asyncio
from pathlib import Path
import socket

from aiohomekit.controller.controller import Controller
from aiohomekit.controller.ip.discovery import IpDiscovery
from aiohomekit.zeroconf import HomeKitService
from homeassistant import config_entries

from custom_components.homekit_manager.migration_engine import MigrationEngine, MigrationPlan
from custom_components.homekit_manager.migration_journal import JournalStore
from custom_components.homekit_manager.migration_lock import BridgeMigrationLock
from custom_components.homekit_manager.migration_snapshot import MigrationSnapshot, SnapshotStore


class LocalAdvertiser:
    async def async_register_service(self, _service, **_kwargs):
        return None

    async def async_unregister_service(self, _service):
        return None

    async def async_update_service(self, _service):
        return None

    async def async_close(self):
        return None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]


async def _pair(entry, label: str):
    homekit = entry.runtime_data.homekit
    controller = Controller()
    discovery = IpDiscovery(controller, HomeKitService.from_service_info(homekit.driver.mdns_service_info))
    try:
        finish = await asyncio.wait_for(discovery.async_start_pairing(label), 10)
        pairing = await asyncio.wait_for(finish(homekit.driver.state.pincode.decode()), 10)
    finally:
        await discovery.close()
    await homekit.hass.async_add_executor_job(homekit.driver.persist)
    accessories = await asyncio.wait_for(pairing.list_accessories_and_characteristics(), 10)
    identity = {
        "mac": homekit.driver.state.mac,
        "aids": sorted(item["aid"] for item in accessories),
        "pairing_data": dict(pairing.pairing_data),
    }
    await pairing.shutdown()
    return controller, identity


async def _observe(controller: Controller, pairing_data: dict, identity: dict) -> None:
    from aiohomekit.controller.ip.pairing import IpPairing

    pairing = IpPairing(controller, pairing_data)
    accessories = await asyncio.wait_for(pairing.list_accessories_and_characteristics(), 10)
    assert sorted(item["aid"] for item in accessories) == identity["aids"]
    await pairing.shutdown()


async def test_two_real_hap_bridges_isolate_migration_and_pairings(hass, monkeypatch, socket_enabled):
    from homeassistant.components.homekit import HomeKit

    async def local_advertiser(_hass):
        return LocalAdvertiser()

    monkeypatch.setattr("homeassistant.components.homekit.zeroconf.async_get_async_instance", local_advertiser)
    monkeypatch.setattr(HomeKit, "_async_show_setup_message", lambda _self: None)
    Path(hass.config.path(".storage")).mkdir(mode=0o700, exist_ok=True)
    hass.states.async_set("input_boolean.bridge_a", "off")
    hass.states.async_set("input_boolean.bridge_b", "off")
    await hass.async_block_till_done()

    port_a, port_b = _free_port(), _free_port()
    entry_a = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="Bridge A",
        data={"name": "Bridge A", "port": port_a, "ip_address": "127.0.0.1", "advertise_ip": ["127.0.0.1"]},
        options={"mode": "bridge", "filter": {"include_entities": ["input_boolean.bridge_a"]}},
        source=config_entries.SOURCE_USER, entry_id="isolated-multi-bridge-a", unique_id=None,
        discovery_keys={}, subentries_data=None,
    )
    entry_b = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="Bridge B",
        data={"name": "Bridge B", "port": port_b, "ip_address": "127.0.0.1", "advertise_ip": ["127.0.0.1"]},
        options={"mode": "bridge", "filter": {"include_entities": ["input_boolean.bridge_b"]}},
        source=config_entries.SOURCE_USER, entry_id="isolated-multi-bridge-b", unique_id=None,
        discovery_keys={}, subentries_data=None,
    )
    await hass.config_entries.async_add(entry_a)
    await hass.config_entries.async_add(entry_b)
    await hass.async_block_till_done()
    assert entry_a.state.value == entry_b.state.value == "loaded"
    controller_a, identity_a = await _pair(entry_a, "bridge-a")
    controller_b, identity_b = await _pair(entry_b, "bridge-b")

    source_file = Path(hass.config.path("configuration.yaml"))
    source_file.write_text("homekit: []\n", encoding="utf-8")
    snapshot = MigrationSnapshot.build(
        transaction_id="pending", bridge_id=entry_a.entry_id,
        logical={"entry_id": entry_a.entry_id, "source": "user", "target": "import", "mac": identity_a["mac"]},
        files={"configuration.yaml": source_file},
    )
    engine = MigrationEngine(
        journal=JournalStore(Path(hass.config.path(".storage/multi-bridge.journal.json"))),
        snapshots=SnapshotStore(Path(hass.config.path(".storage/multi-bridge.snapshot.json"))),
        lock=BridgeMigrationLock(Path(hass.config.path(".storage/multi-bridge.lock")), entry_a.entry_id),
        experimental_test_permit=True,
    )

    async def quiesce():
        assert await hass.config_entries.async_unload(entry_a.entry_id)

    async def source_switch():
        entry_a.source = config_entries.SOURCE_IMPORT
        hass.config_entries.async_update_entry(entry_a, data={"name": "Bridge A", "port": port_a})
        await hass.config_entries._store.async_save(hass.config_entries._data_to_save())

    async def reload():
        assert await hass.config_entries.async_setup(entry_a.entry_id)
        await hass.async_block_till_done()

    async def verify():
        await _observe(controller_a, identity_a["pairing_data"], identity_a)
        await _observe(controller_b, identity_b["pairing_data"], identity_b)
        assert entry_a.runtime_data.homekit.driver.state.mac == identity_a["mac"]
        assert entry_b.runtime_data.homekit.driver.state.mac == identity_b["mac"]

    await engine.execute_async(
        MigrationPlan(entry_a.entry_id, "user", "import", snapshot.fingerprint, "multi-bridge-revision"),
        steps={"quiesce": quiesce, "source_switch": source_switch, "reload": reload, "verify": verify},
        snapshot=snapshot,
        expected_revision=lambda: "multi-bridge-revision",
    )
