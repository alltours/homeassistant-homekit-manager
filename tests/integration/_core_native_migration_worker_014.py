"""Full-Core 0.10.14 migration worker used only with the patched Core checkout.

Each invocation is one isolated process phase.  Migration phases intentionally
terminate with SIGKILL after Core has durably switched the source; the next
invocation exercises the normal Home Assistant startup path, not a harness
recovery callback.
"""
from __future__ import annotations

import asyncio
import gc
import json
import os
import signal
import socket
from pathlib import Path
from unittest.mock import patch

from aiohomekit.controller.controller import Controller
from aiohomekit.controller.ip.discovery import IpDiscovery
from aiohomekit.controller.ip.pairing import IpPairing
from aiohomekit.zeroconf import HomeKitService
from homeassistant import config_entries
from homeassistant.bootstrap import async_setup_hass
from homeassistant.components.homekit import HomeKit
from homeassistant.runner import RuntimeConfig

from custom_components.homekit_manager.core_migration import (
    async_prepare,
    async_switch,
)

ENTITY_ID = "input_boolean.migration_test"
ENTRY_ID = "isolated-core-migration-014"


class LocalAdvertiser:
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


def write_configuration(shared: Path, *, yaml_bridge: bool, name: str, port: int) -> None:
    content = (
        "homeassistant:\n  name: Isolated Core Migration\n"
        "input_boolean:\n  migration_test:\n    name: Migration Test\n"
        "logger:\n  default: critical\n"
    )
    if yaml_bridge:
        content += (
            "homekit:\n"
            f"  - name: {name}\n"
            f"    port: {port}\n"
            "    ip_address: 127.0.0.1\n"
            "    advertise_ip:\n      - 127.0.0.1\n"
            "    filter:\n"
            f"      include_entities:\n        - {ENTITY_ID}\n"
        )
    (shared / "configuration.yaml").write_text(content, encoding="utf-8")


async def boot(shared: Path):
    hass = await async_setup_hass(
        RuntimeConfig(config_dir=str(shared), skip_pip=True, log_file=str(shared / "home-assistant.log"))
    )
    assert hass is not None
    await hass.async_block_till_done()
    hass.states.async_set(ENTITY_ID, "off")
    await hass.async_block_till_done()
    return hass


async def loaded_entry(hass, expected_source: str | None = None):
    for _ in range(100):
        entries = hass.config_entries.async_entries("homekit")
        if len(entries) == 1 and (expected_source is None or entries[0].source == expected_source):
            entry = entries[0]
            if entry.state.value != "loaded":
                await hass.config_entries.async_setup(entry.entry_id)
                await hass.async_block_till_done()
            if entry.state.value == "loaded":
                return entry
        await asyncio.sleep(0.05)
    entries = hass.config_entries.async_entries("homekit")
    raise AssertionError(
        "HomeKit entry did not reach the expected loaded state: "
        + repr([(entry.entry_id, entry.source, entry.state.value, entry.reason) for entry in entries])
    )


def identity(entry, accessories) -> dict:
    homekit = entry.runtime_data.homekit
    aid = homekit.aid_storage.get_allocated_aid_for_entity_id(ENTITY_ID)
    assert aid is not None
    return {
        "entry_id": entry.entry_id,
        "source": entry.source,
        "name": entry.data["name"],
        "port": entry.data["port"],
        "mac": homekit.driver.state.mac,
        "aid": aid,
        "iids": sorted(
            iid
            for accessory in accessories
            if accessory["aid"] == aid
            for service in accessory["services"]
            for iid in [service["iid"], *(characteristic["iid"] for characteristic in service["characteristics"])]
        ),
        "allowlist": sorted(entry.options.get("filter", {}).get("include_entities", [])),
    }


async def pair_and_record(shared: Path, entry) -> None:
    homekit = entry.runtime_data.homekit
    controller = Controller()
    discovery = IpDiscovery(controller, HomeKitService.from_service_info(homekit.driver.mdns_service_info))
    try:
        finish = await asyncio.wait_for(discovery.async_start_pairing("core-migration-014"), 10)
        pairing = await asyncio.wait_for(finish(homekit.driver.state.pincode.decode()), 10)
    finally:
        await discovery.close()
    await entry.runtime_data.homekit.hass.async_add_executor_job(homekit.driver.persist)
    accessories = await asyncio.wait_for(pairing.list_accessories_and_characteristics(), 10)
    assert accessories
    (shared / "controller_pairing.json").write_text(json.dumps(pairing.pairing_data), encoding="utf-8")
    (shared / "baseline.json").write_text(json.dumps(identity(entry, accessories)), encoding="utf-8")
    (shared / "baseline_accessories.json").write_text(json.dumps(accessories), encoding="utf-8")
    await pairing.shutdown()


async def verify_hap(shared: Path, entry) -> None:
    baseline = json.loads((shared / "baseline.json").read_text(encoding="utf-8"))
    controller = Controller()
    pairing = IpPairing(controller, json.loads((shared / "controller_pairing.json").read_text(encoding="utf-8")))
    accessories = await asyncio.wait_for(pairing.list_accessories_and_characteristics(), 10)
    current = identity(entry, accessories)
    for key in ("entry_id", "name", "port", "mac", "aid", "iids", "allowlist"):
        assert current[key] == baseline[key], (key, current[key], baseline[key])
    expected = json.loads((shared / "baseline_accessories.json").read_text(encoding="utf-8"))
    assert [(item["aid"], item["services"]) for item in accessories] == [
        (item["aid"], item["services"]) for item in expected
    ]
    await pairing.shutdown()


async def run() -> None:
    shared = Path(os.environ["HKM_CORE_MIGRATION_DIR"])
    direction = os.environ["HKM_CORE_MIGRATION_DIRECTION"]
    phase = os.environ["HKM_CORE_MIGRATION_PHASE"]
    name = "Core Migration UI" if direction == "ui_to_yaml" else "Core Migration YAML"
    yaml_bridge = direction == "yaml_to_ui"
    if phase == "pair":
        port = free_loopback_port()
        write_configuration(shared, yaml_bridge=yaml_bridge, name=name, port=port)
    elif phase == "migrate":
        baseline = json.loads((shared / "baseline.json").read_text(encoding="utf-8"))
        port = baseline["port"]
        # Keep the original source configuration for bootstrap.  The target
        # YAML is written only after Core is running, otherwise native
        # reconciliation could create a second bridge before the transaction
        # journal exists.
    elif phase in {"verify", "verify_stale"}:
        baseline = json.loads((shared / "baseline.json").read_text(encoding="utf-8"))
        write_configuration(
            shared,
            yaml_bridge=(direction == "ui_to_yaml" or phase == "verify_stale"),
            name=name,
            port=baseline["port"],
        )

    with (
        patch("homeassistant.components.homekit.zeroconf.async_get_async_instance", local_advertiser),
        patch.object(HomeKit, "_async_show_setup_message", lambda _self: None),
    ):
        hass = await boot(shared)
        if phase == "pair":
            if yaml_bridge:
                await hass.async_start()
                await hass.async_block_till_done()
                entry = await loaded_entry(hass, config_entries.SOURCE_IMPORT)
            else:
                entry = config_entries.ConfigEntry(
                    version=1, minor_version=1, domain="homekit", title=name,
                    data={"name": name, "port": port, "ip_address": "127.0.0.1", "advertise_ip": ["127.0.0.1"]},
                    options={"mode": "bridge", "filter": {"include_entities": [ENTITY_ID]}},
                    source=config_entries.SOURCE_USER, entry_id=ENTRY_ID, unique_id=None,
                    discovery_keys={}, subentries_data=None,
                )
                await hass.config_entries.async_add(entry)
                await hass.config_entries._store.async_save(hass.config_entries._data_to_save())
                await hass.async_start()
                await hass.async_block_till_done()
                if entry.state.value != "loaded":
                    await hass.config_entries.async_setup(entry.entry_id)
                    await hass.async_block_till_done()
            await hass.async_block_till_done()
            await pair_and_record(shared, entry)
            await hass.async_stop(force=True)
            return

        await hass.async_start()
        await hass.async_block_till_done()
        original_source = config_entries.SOURCE_USER if direction == "ui_to_yaml" else config_entries.SOURCE_IMPORT
        target_source = config_entries.SOURCE_IMPORT if direction == "ui_to_yaml" else config_entries.SOURCE_USER
        entry = await loaded_entry(hass, original_source if phase == "migrate" else target_source)
        if phase == "migrate":
            write_configuration(shared, yaml_bridge=(direction == "ui_to_yaml"), name=name, port=entry.data["port"])
            baseline_mac = entry.runtime_data.homekit.driver.state.mac
            await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()
            target = config_entries.SOURCE_IMPORT if direction == "ui_to_yaml" else config_entries.SOURCE_USER
            target_data = {"name": name, "port": entry.data["port"]}
            if target == config_entries.SOURCE_IMPORT:
                target_data.update({"ip_address": "127.0.0.1", "advertise_ip": ["127.0.0.1"]})
            request = {
                "schema_version": 1,
                "transaction_id": f"tx-{direction}",
                "entry_id": entry.entry_id,
                "source": entry.source,
                "target": target,
                "state": "PREPARED",
                "name": name,
                "port": entry.data["port"],
                "target_data": target_data,
                "target_options": dict(entry.options),
                "baseline_fingerprint": "preflight",
                "allowlist": [ENTITY_ID],
                "mac": baseline_mac,
            }
            prepared = await async_prepare(hass, request)
            assert prepared["state"] == "PREPARED", prepared
            switched = await async_switch(hass, request["transaction_id"])
            assert switched["state"] == "SOURCE_SWITCHED", switched
            await hass.async_block_till_done()
            os.kill(os.getpid(), signal.SIGKILL)

        await verify_hap(shared, entry)
        await hass.async_stop(force=True)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except BaseException as err:
        print(f"WORKER_FAILURE {type(err).__name__}: {err!r}", flush=True)
        raise
    gc.freeze()
