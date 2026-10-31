"""Isolated proof of concept for native HomeKit source switching.

This worker intentionally exercises an unsupported Core-internal operation:
ConfigEntry.source is assigned directly and the config-entry store is saved.
It is test evidence only and is never imported by the production integration.
Pairing material stays in the caller's temporary directory and is never logged.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
from pathlib import Path

import pytest
from aiohomekit.controller.controller import Controller
from aiohomekit.controller.ip.discovery import IpDiscovery
from aiohomekit.controller.ip.pairing import IpPairing
from aiohomekit.zeroconf import HomeKitService
from homeassistant import config_entries
from homeassistant.config import async_hass_config_yaml
from homeassistant.const import __version__
from homeassistant.setup import async_setup_component

ENTRY_ID = "isolated-native-source-migration"
ENTITY_ID = "input_boolean.native_migration_test"
BRIDGE_NAME = "Native Source Migration"


class LocalAdvertiser:
    """Suppress mDNS publication while retaining a real loopback HAP server."""

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


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]


def _yaml_source(port: int) -> str:
    return (
        "homekit: !include native_migration.yaml\n"
        "input_boolean:\n"
        "  native_migration_test:\n"
        "    name: Native migration test\n"
    )


def _yaml_fragment(port: int) -> str:
    return (
        f"- name: {BRIDGE_NAME}\n"
        f"  port: {port}\n"
        "  ip_address: 127.0.0.1\n"
        "  advertise_ip:\n"
        "    - 127.0.0.1\n"
        "  filter:\n"
        f"    include_entities:\n    - {ENTITY_ID}\n"
    )


def _base_config() -> str:
    return (
        "input_boolean:\n"
        "  native_migration_test:\n"
        "    name: Native migration test\n"
    )


async def _save_config_entries(hass) -> None:
    """Persist the test-only ConfigEntry source mutation."""
    await hass.config_entries._store.async_save(
        hass.config_entries._data_to_save()
    )


async def _unload_for_source_change(hass, entry) -> None:
    """Quiesce the isolated bridge before the unsupported source mutation."""
    from homeassistant.components.homekit.util import async_port_is_available

    assert await hass.config_entries.async_unload(entry.entry_id)
    for _ in range(100):
        if async_port_is_available(entry.data["port"]):
            return
        await asyncio.sleep(0.05)
    raise AssertionError("HAP port did not become available after isolated unload")


async def _prepare_hass(hass, shared: Path, yaml_enabled: bool):
    """Load only the isolated test storage and the selected source."""
    hass.config.config_dir = str(shared)
    hass.states.async_set(ENTITY_ID, "off")
    await hass.async_block_till_done()
    (shared / ".storage").mkdir(mode=0o700, exist_ok=True)
    (shared / "configuration.yaml").write_text(
        _yaml_source(0) if yaml_enabled else _base_config(), encoding="utf-8"
    )
    if yaml_enabled:
        identity = json.loads((shared / "public_identity.json").read_text())
        (shared / "configuration.yaml").write_text(
            _yaml_source(identity["port"]), encoding="utf-8"
        )
        (shared / "native_migration.yaml").write_text(
            _yaml_fragment(identity["port"]), encoding="utf-8"
        )

    hass.config_entries = config_entries.ConfigEntries(hass, {"_": "native migration"})
    await hass.config_entries.async_initialize()
    if yaml_enabled:
        await async_setup_component(
            hass, "homekit", await async_hass_config_yaml(hass)
        )
        await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(ENTRY_ID)
    assert entry is not None
    if entry.state.value != "loaded":
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state.value == "loaded"
    return entry


async def _pair_or_reconnect(hass, shared: Path, entry, pair: bool):
    """Pair or reconnect and return a redacted identity observation."""
    from homeassistant.components.homekit.util import (
        get_aid_storage_filename_for_entry_id,
        get_iid_storage_filename_for_entry_id,
        get_persist_fullpath_for_entry_id,
    )

    homekit = entry.runtime_data.homekit
    assert homekit.driver is not None and homekit.status == 1
    aid = homekit.aid_storage.get_allocated_aid_for_entity_id(ENTITY_ID)
    assert aid is not None
    await homekit.aid_storage.async_save()
    await homekit.iid_storage.async_save()
    assert Path(get_persist_fullpath_for_entry_id(hass, entry.entry_id)).is_file()
    assert Path(hass.config.path(".storage", get_aid_storage_filename_for_entry_id(entry.entry_id))).is_file()
    assert Path(hass.config.path(".storage", get_iid_storage_filename_for_entry_id(entry.entry_id))).is_file()

    controller = Controller()
    if pair:
        discovery = IpDiscovery(
            controller,
            HomeKitService.from_service_info(homekit.driver.mdns_service_info),
        )
        try:
            finish = await asyncio.wait_for(
                discovery.async_start_pairing("native-source-migration"), 10
            )
            pairing = await asyncio.wait_for(
                finish(homekit.driver.state.pincode.decode()), 10
            )
        finally:
            await discovery.close()
        await hass.async_add_executor_job(homekit.driver.persist)
        pairing_data = dict(pairing.pairing_data)
        (shared / "controller_pairing.json").write_text(
            json.dumps(pairing_data), encoding="utf-8"
        )
        (shared / "controller_pairing.json").chmod(0o600)
    else:
        assert homekit.driver.state.paired
        pairing = IpPairing(
            controller,
            json.loads((shared / "controller_pairing.json").read_text()),
        )

    accessories = await asyncio.wait_for(
        pairing.list_accessories_and_characteristics(), 10
    )
    try:
        accessory = next(item for item in accessories if item["aid"] == aid)
    except StopIteration as err:
        raise AssertionError(
            f"HAP entity accessory missing: expected aid={aid}, "
            f"received aids={[item.get('aid') for item in accessories]}, "
            f"source={entry.source}"
        ) from err
    iids = sorted(
        iid
        for service in accessory["services"]
        for iid in [service["iid"], *(char["iid"] for char in service["characteristics"])]
    )
    observation = {
        "entry_id": entry.entry_id,
        "source": entry.source,
        "mac": homekit.driver.state.mac,
        "paired": homekit.driver.state.paired,
        "aids": sorted(item["aid"] for item in accessories),
        "entity_aid": aid,
        "entity_iids": iids,
        "core": __version__,
    }
    await pairing.shutdown()
    return observation


@pytest.mark.asyncio
async def test_worker(hass, monkeypatch, socket_enabled):
    """Run one phase of the isolated UI/YAML source migration experiment."""
    from homeassistant.components.homekit import HomeKit
    from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER

    shared = Path(os.environ["HKM_NATIVE_SOURCE_MIGRATION_DIR"])
    phase = os.environ["HKM_NATIVE_SOURCE_MIGRATION_PHASE"]
    advertiser = LocalAdvertiser()

    async def local_advertiser(_hass):
        return advertiser

    async def local_addresses(_hass):
        return ["127.0.0.1"]

    monkeypatch.setattr(
        "homeassistant.components.homekit.zeroconf.async_get_async_instance",
        local_advertiser,
    )
    monkeypatch.setattr(
        "homeassistant.components.homekit.network.async_get_announce_addresses",
        local_addresses,
    )
    monkeypatch.setattr(HomeKit, "_async_show_setup_message", lambda _self: None)

    if phase == "pair_ui":
        shared.mkdir(mode=0o700, exist_ok=True)
        port = _free_port()
        (shared / "configuration.yaml").write_text(_base_config(), encoding="utf-8")
        hass.config.config_dir = str(shared)
        (shared / ".storage").mkdir(mode=0o700, exist_ok=True)
        hass.config_entries = config_entries.ConfigEntries(hass, {"_": "native migration"})
        entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain="homekit",
            title=f"{BRIDGE_NAME}:{port}",
            data={"name": BRIDGE_NAME, "port": port},
            options={"mode": "bridge", "filter": {"include_entities": [ENTITY_ID]}},
            source=SOURCE_USER,
            entry_id=ENTRY_ID,
            unique_id=None,
            discovery_keys={},
            subentries_data=None,
        )
        hass.states.async_set(ENTITY_ID, "off")
        await hass.async_block_till_done()
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        assert entry.state.value == "loaded"
        observation = await _pair_or_reconnect(hass, shared, entry, True)
        observation["source"] = entry.source
        (shared / "public_identity.json").write_text(
            json.dumps({"port": port, **observation}), encoding="utf-8"
        )
        await _save_config_entries(hass)
        await entry.runtime_data.homekit.async_stop()
        return

    identity = json.loads((shared / "public_identity.json").read_text())
    yaml_enabled = phase in {"restart_yaml", "migrate_yaml_ui"}
    entry = await _prepare_hass(hass, shared, yaml_enabled)
    before = await _pair_or_reconnect(hass, shared, entry, False)

    if phase == "migrate_ui_yaml":
        assert entry.source == SOURCE_USER
        (shared / "configuration.yaml").write_text(
            _yaml_source(identity["port"]), encoding="utf-8"
        )
        (shared / "native_migration.yaml").write_text(
            _yaml_fragment(identity["port"]), encoding="utf-8"
        )
        await _unload_for_source_change(hass, entry)
        entry.source = SOURCE_IMPORT
        await _save_config_entries(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        after = await _pair_or_reconnect(hass, shared, entry, False)
        assert after["source"] == SOURCE_IMPORT
        assert after["entry_id"] == before["entry_id"] == identity["entry_id"]
        assert after["mac"] == before["mac"] == identity["mac"]
        assert after["aids"] == before["aids"] == identity["aids"]
        assert after["entity_iids"] == before["entity_iids"] == identity["entity_iids"]
    elif phase == "restart_yaml":
        assert entry.source == SOURCE_IMPORT
        assert before["source"] == SOURCE_IMPORT
        assert before["entry_id"] == identity["entry_id"]
        assert before["mac"] == identity["mac"]
        assert before["aids"] == identity["aids"]
        assert before["entity_iids"] == identity["entity_iids"]
    elif phase == "migrate_yaml_ui":
        assert entry.source == SOURCE_IMPORT
        (shared / "configuration.yaml").write_text(_base_config(), encoding="utf-8")
        (shared / "native_migration.yaml").unlink()
        await _unload_for_source_change(hass, entry)
        entry.source = SOURCE_USER
        hass.config_entries.async_update_entry(
            entry,
            data={"name": BRIDGE_NAME, "port": identity["port"]},
            options={"mode": "bridge", "filter": {"include_entities": [ENTITY_ID]}},
        )
        await _save_config_entries(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        after = await _pair_or_reconnect(hass, shared, entry, False)
        assert after["source"] == SOURCE_USER
        assert after["entry_id"] == before["entry_id"] == identity["entry_id"]
        assert after["mac"] == before["mac"] == identity["mac"]
        assert after["aids"] == before["aids"] == identity["aids"]
        assert after["entity_iids"] == before["entity_iids"] == identity["entity_iids"]
    elif phase == "restart_ui":
        assert entry.source == SOURCE_USER
        assert before["source"] == SOURCE_USER
        assert before["entry_id"] == identity["entry_id"]
        assert before["mac"] == identity["mac"]
        assert before["aids"] == identity["aids"]
        assert before["entity_iids"] == identity["entity_iids"]
    else:
        raise AssertionError(f"Unknown migration phase: {phase}")

    await entry.runtime_data.homekit.async_stop()
