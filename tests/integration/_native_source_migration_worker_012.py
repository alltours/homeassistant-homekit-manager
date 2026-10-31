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
import signal
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

from custom_components.homekit_manager.migration_engine import (
    MigrationEngine,
    MigrationPlan,
)
from custom_components.homekit_manager.migration_journal import JournalStore
from custom_components.homekit_manager.migration_lock import BridgeMigrationLock
from custom_components.homekit_manager.migration_snapshot import (
    MigrationSnapshot,
    SnapshotStore,
)

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
    if os.environ.get("HKM_NATIVE_SOURCE_MIGRATION_FAULT") == "DURING_UNLOAD":
        (Path(hass.config.config_dir) / "fault-reached").write_text("DURING_UNLOAD", encoding="utf-8")
        os.kill(os.getpid(), signal.SIGKILL)
    for _ in range(100):
        if async_port_is_available(entry.data["port"]):
            return
        await asyncio.sleep(0.05)
    raise AssertionError("HAP port did not become available after isolated unload")


async def _run_engine_source_switch(hass, shared: Path, entry, identity: dict, before: dict, target: str):
    """Run the durable engine around the test-only Core source mutation."""
    from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER

    source = SOURCE_USER if entry.source == SOURCE_USER else SOURCE_IMPORT
    target_source = SOURCE_IMPORT if target == SOURCE_IMPORT else SOURCE_USER
    snapshot = MigrationSnapshot.build(
        transaction_id="pending",
        bridge_id=entry.entry_id,
        logical={
            "entry_id": entry.entry_id,
            "source": source,
            "target": target_source,
            "mac": before["mac"],
            "aids": before["aids"],
            "iids": before["entity_iids"],
        },
        files={"configuration.yaml": shared / "configuration.yaml"},
    )
    engine = MigrationEngine(
        journal=JournalStore(shared / "migration.journal.json"),
        snapshots=SnapshotStore(shared / "migration.snapshot.json"),
        lock=BridgeMigrationLock(shared / "migration.bridge.lock", entry.entry_id),
        experimental_test_permit=True,
        fault_injector=lambda point: _inject_fault(shared, point),
    )

    async def quiesce():
        await _unload_for_source_change(hass, entry)

    async def source_switch():
        if target_source == SOURCE_IMPORT:
            _inject_fault(shared, "BEFORE_YAML_WRITE")
            (shared / "configuration.yaml").write_text(
                _yaml_source(identity["port"]), encoding="utf-8"
            )
            (shared / "native_migration.yaml").write_text(
                _yaml_fragment(identity["port"]), encoding="utf-8"
            )
            _inject_fault(shared, "AFTER_YAML_WRITE")
            entry.source = SOURCE_IMPORT
        else:
            _inject_fault(shared, "BEFORE_YAML_WRITE")
            (shared / "configuration.yaml").write_text(_base_config(), encoding="utf-8")
            (shared / "native_migration.yaml").unlink()
            _inject_fault(shared, "AFTER_YAML_WRITE")
            entry.source = SOURCE_USER
            hass.config_entries.async_update_entry(
                entry,
                data={"name": BRIDGE_NAME, "port": identity["port"]},
                options={"mode": "bridge", "filter": {"include_entities": [ENTITY_ID]}},
            )
        await _save_config_entries(hass)

    async def reload():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    async def verify():
        after = await _pair_or_reconnect(hass, shared, entry, False)
        assert after["source"] == target_source
        assert after["entry_id"] == before["entry_id"] == identity["entry_id"]
        assert after["mac"] == before["mac"] == identity["mac"]
        assert after["aids"] == before["aids"] == identity["aids"]
        assert after["entity_iids"] == before["entity_iids"] == identity["entity_iids"]

    async def noop():
        return None

    result = await engine.execute_async(
        MigrationPlan(
            bridge_id=entry.entry_id,
            source=source,
            target=target_source,
            baseline_fingerprint=snapshot.fingerprint,
            config_revision=identity["entry_id"],
        ),
        steps={
            "lock": noop,
            "snapshot": noop,
            "prepare": noop,
            "quiesce": quiesce,
            "source_switch": source_switch,
            "reload": reload,
            "verify": verify,
            "commit": noop,
        },
        snapshot=snapshot,
        expected_revision=lambda: identity["entry_id"],
    )
    assert result.state == "COMMITTED"


def _inject_fault(shared: Path, point: str) -> None:
    """Kill only when the requested isolated worker fault point is reached."""
    if os.environ.get("HKM_NATIVE_SOURCE_MIGRATION_FAULT") != point:
        return
    state_filter = os.environ.get("HKM_NATIVE_SOURCE_MIGRATION_FAULT_STATE")
    if state_filter:
        record = JournalStore(shared / "migration.journal.json").load()
        if record is None or record.state != state_filter:
            return
    (shared / "fault-reached").write_text(point, encoding="utf-8")
    os.kill(os.getpid(), signal.SIGKILL)


async def _prepare_hass(hass, shared: Path, yaml_enabled: bool, preserve_files: bool = False):
    """Load only the isolated test storage and the selected source."""
    hass.config.config_dir = str(shared)
    hass.states.async_set(ENTITY_ID, "off")
    await hass.async_block_till_done()
    (shared / ".storage").mkdir(mode=0o700, exist_ok=True)
    if not preserve_files:
        (shared / "configuration.yaml").write_text(
            _yaml_source(0) if yaml_enabled else _base_config(), encoding="utf-8"
        )
    if yaml_enabled and not preserve_files:
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
    expected_entry_id = ENTRY_ID
    identity_path = shared / "public_identity.json"
    if identity_path.exists():
        expected_entry_id = json.loads(identity_path.read_text(encoding="utf-8")).get(
            "entry_id", ENTRY_ID
        )
    entry = hass.config_entries.async_get_entry(expected_entry_id)
    if entry is None and yaml_enabled:
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        entry = next(
            (
                candidate
                for candidate in hass.config_entries.async_entries("homekit")
                if candidate.data.get("port") == identity["port"]
            ),
            None,
        )
    assert entry is not None
    if entry.state.value != "loaded":
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state.value == "loaded"
    return entry


async def _recover_after_crash(hass, shared: Path, entry, identity: dict) -> None:
    """Recover an interrupted isolated migration after a real Core crash."""
    store = JournalStore(shared / "migration.journal.json")
    record = store.load()
    assert record is not None
    original = await _pair_or_reconnect(hass, shared, entry, False)
    original_source = identity.get("source", config_entries.SOURCE_USER)

    if record.state in {"PREFLIGHT", "LOCKED", "SNAPSHOT_CREATED", "PREPARED"}:
        assert entry.source == original_source
        assert original["mac"] == identity["mac"]
        store.save(record.advance(
            state="FAILED",
            completed_operation="recovery_complete",
            recovery_status="RECOVERY_COMPLETED",
        ))
        return

    # A crash after quiescing or source/YAML mutation is resolved by an
    # explicitly journaled rollback. Recovery never recreates a bridge.
    store.save(record.advance(
        state="ROLLING_BACK",
        completed_operation="recovery_start",
        recovery_status="ROLLBACK_REQUIRED",
    ))
    if os.environ.get("HKM_NATIVE_SOURCE_MIGRATION_FAULT") == "DURING_ROLLBACK":
        (shared / "fault-reached").write_text("DURING_ROLLBACK", encoding="utf-8")
        os.kill(os.getpid(), signal.SIGKILL)
    assert await hass.config_entries.async_unload(entry.entry_id)
    from homeassistant.components.homekit.util import async_port_is_available

    for _ in range(100):
        if async_port_is_available(entry.data["port"]):
            break
        await asyncio.sleep(0.05)
    if original_source == config_entries.SOURCE_IMPORT:
        (shared / "configuration.yaml").write_text(
            (shared / "baseline_configuration.yaml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        baseline_fragment = shared / "baseline_native_migration.yaml"
        if baseline_fragment.exists():
            (shared / "native_migration.yaml").write_text(
                baseline_fragment.read_text(encoding="utf-8"), encoding="utf-8"
            )
    else:
        (shared / "configuration.yaml").write_text(_base_config(), encoding="utf-8")
    fragment = shared / "native_migration.yaml"
    if original_source != config_entries.SOURCE_IMPORT and fragment.exists():
        fragment.unlink()
    entry.source = original_source
    if original_source == config_entries.SOURCE_USER:
        hass.config_entries.async_update_entry(
            entry,
            data={"name": BRIDGE_NAME, "port": identity["port"]},
            options={"mode": "bridge", "filter": {"include_entities": [ENTITY_ID]}},
        )
    await _save_config_entries(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    restored = await _pair_or_reconnect(hass, shared, entry, False)
    assert restored["entry_id"] == identity["entry_id"]
    assert restored["source"] == original_source
    assert restored["mac"] == identity["mac"]
    assert restored["aids"] == identity["aids"]
    assert restored["entity_iids"] == identity["entity_iids"]
    store.save((store.load() or record).advance(
        state="ROLLED_BACK",
        completed_operation="rollback_complete",
        recovery_status="ROLLBACK_COMPLETED",
    ))


async def _pair_or_reconnect(hass, shared: Path, entry, pair: bool):
    """Pair or reconnect and return a redacted identity observation."""
    from homeassistant.components.homekit.util import (
        get_aid_storage_filename_for_entry_id,
        get_iid_storage_filename_for_entry_id,
        get_persist_fullpath_for_entry_id,
    )

    homekit = entry.runtime_data.homekit
    assert homekit.driver is not None and homekit.status == 1
    if pair:
        assert not homekit.driver.state.paired
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

    if phase in {"pair_ui", "pair_yaml"}:
        shared.mkdir(mode=0o700, exist_ok=True)
        port = _free_port()
        yaml_pairing = phase == "pair_yaml"
        (shared / "configuration.yaml").write_text(
            _yaml_source(port) if yaml_pairing else _base_config(), encoding="utf-8"
        )
        if yaml_pairing:
            (shared / "native_migration.yaml").write_text(
                _yaml_fragment(port), encoding="utf-8"
            )
            (shared / "baseline_configuration.yaml").write_text(
                _yaml_source(port), encoding="utf-8"
            )
            (shared / "baseline_native_migration.yaml").write_text(
                _yaml_fragment(port), encoding="utf-8"
            )
        hass.config.config_dir = str(shared)
        (shared / ".storage").mkdir(mode=0o700, exist_ok=True)
        hass.config_entries = config_entries.ConfigEntries(hass, {"_": "native migration"})
        hass.states.async_set(ENTITY_ID, "off")
        await hass.async_block_till_done()
        if yaml_pairing:
            await async_setup_component(
                hass, "homekit", await async_hass_config_yaml(hass)
            )
            await hass.async_block_till_done()
            entry = next(
                candidate
                for candidate in hass.config_entries.async_entries("homekit")
                if candidate.data.get("port") == port
            )
        else:
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
    yaml_enabled = (
        (shared / "native_migration.yaml").exists()
        if phase == "recover"
        else phase in {"restart_yaml", "migrate_yaml_ui"}
    )
    entry = await _prepare_hass(hass, shared, yaml_enabled, preserve_files=phase == "recover")
    before = await _pair_or_reconnect(hass, shared, entry, False)

    if phase == "recover":
        await _recover_after_crash(hass, shared, entry, identity)
    elif phase == "migrate_ui_yaml":
        assert entry.source == SOURCE_USER
        await _run_engine_source_switch(hass, shared, entry, identity, before, SOURCE_IMPORT)
    elif phase == "restart_yaml":
        assert entry.source == SOURCE_IMPORT
        assert before["source"] == SOURCE_IMPORT
        assert before["entry_id"] == identity["entry_id"]
        assert before["mac"] == identity["mac"]
        assert before["aids"] == identity["aids"]
        assert before["entity_iids"] == identity["entity_iids"]
    elif phase == "migrate_yaml_ui":
        assert entry.source == SOURCE_IMPORT
        await _run_engine_source_switch(hass, shared, entry, identity, before, SOURCE_USER)
    elif phase == "restart_ui":
        assert entry.source == SOURCE_USER
        assert [
            candidate.entry_id
            for candidate in hass.config_entries.async_entries("homekit")
        ] == [entry.entry_id]
        assert before["source"] == SOURCE_USER
        assert before["entry_id"] == identity["entry_id"]
        assert before["mac"] == identity["mac"]
        assert before["aids"] == identity["aids"]
        assert before["entity_iids"] == identity["entity_iids"]
    else:
        raise AssertionError(f"Unknown migration phase: {phase}")

    await entry.runtime_data.homekit.async_stop()
