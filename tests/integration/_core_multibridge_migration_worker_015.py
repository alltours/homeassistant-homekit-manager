"""Full-Core two-bridge migration worker for the 0.10.15 experiment.

Every invocation is an isolated Home Assistant process phase.  Pairing data is
kept only in the temporary test directory and is never printed.  The worker
uses the Core-owned pre-reconciliation boundary from the 0.10.14 prototype.
"""
from __future__ import annotations

import asyncio
import gc
import hashlib
import json
import os
import signal
import socket
import traceback
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

ENTITY_A = "input_boolean.multi_bridge_a"
ENTITY_B = "input_boolean.multi_bridge_b"
ENTRY_B = "isolated-multi-bridge-b-015"


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


def _yaml_bridge(name: str, port: int, entity_id: str) -> str:
    return (
        f"  - name: {name}\n"
        f"    port: {port}\n"
        "    ip_address: 127.0.0.1\n"
        "    advertise_ip:\n"
        "      - 127.0.0.1\n"
        "    filter:\n"
        "      include_entities:\n"
        f"        - {entity_id}\n"
    )


def write_configuration(shared: Path, *, yaml_bridge: bool, name: str, port: int) -> None:
    content = (
        "homeassistant:\n  name: Isolated Multi Bridge\n"
        "input_boolean:\n"
        "  multi_bridge_a:\n    name: Multi Bridge A\n"
        "  multi_bridge_b:\n    name: Multi Bridge B\n"
        "logger:\n  default: critical\n"
    )
    if yaml_bridge:
        content += "homekit:\n" + _yaml_bridge(name, port, ENTITY_A)
    (shared / "configuration.yaml").write_text(content, encoding="utf-8")


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _storage_fingerprints(shared: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    storage = shared / ".storage"
    if not storage.is_dir():
        return result
    for path in sorted(storage.glob("*")):
        if path.is_file() and path.name not in {"homekit.migration"}:
            result[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


async def boot(shared: Path):
    hass = await async_setup_hass(
        RuntimeConfig(
            config_dir=str(shared),
            skip_pip=True,
            log_file=str(shared / "home-assistant.log"),
        )
    )
    assert hass is not None
    return hass


async def wait_for_entries(hass, expected_sources: dict[str, str]):
    for _ in range(200):
        entries = hass.config_entries.async_entries("homekit")
        if len(entries) == len(expected_sources):
            by_name = {entry.data.get("name"): entry for entry in entries}
            if all(
                name in by_name
                and by_name[name].source == source
                and by_name[name].state.value == "loaded"
                for name, source in expected_sources.items()
            ):
                return by_name
        await asyncio.sleep(0.05)
    entries = hass.config_entries.async_entries("homekit")
    raise AssertionError(
        "HomeKit entries did not reach the expected state: "
        + repr(
            [
                (
                    entry.entry_id,
                    entry.data.get("name"),
                    entry.source,
                    entry.state.value,
                    entry.reason,
                )
                for entry in entries
            ]
        )
    )


def _accessory_signature(accessories: list[dict]) -> list[list]:
    return [
        [
            accessory["aid"],
            [
                [
                    service["iid"],
                    service["type"],
                    [
                        [characteristic["iid"], characteristic["type"]]
                        for characteristic in service["characteristics"]
                    ],
                ]
                for service in accessory["services"]
            ],
        ]
        for accessory in accessories
    ]


def _logical_identity(entry, accessories: list[dict]) -> dict:
    homekit = entry.runtime_data.homekit
    return {
        "entry_id": entry.entry_id,
        "source": entry.source,
        "name": entry.data["name"],
        "port": entry.data["port"],
        "mac": homekit.driver.state.mac,
        "aids": sorted(item["aid"] for item in accessories),
        "iids": _accessory_signature(accessories),
        "allowlist": sorted(entry.options.get("filter", {}).get("include_entities", [])),
    }


async def _pair(entry, label: str) -> tuple[dict, dict]:
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
    assert accessories
    pairing_data = dict(pairing.pairing_data)
    await pairing.shutdown()
    return pairing_data, {
        "logical": _logical_identity(entry, accessories),
        "accessories": accessories,
        "pairing_fingerprint": _fingerprint(pairing_data),
    }


async def _reconnect(shared: Path, label: str, baseline: dict) -> None:
    file_label = label.lower().replace(" ", "_")
    controller = Controller()
    pairing = IpPairing(
        controller,
        json.loads((shared / f"{file_label}.pairing.json").read_text(encoding="utf-8")),
    )
    accessories = await asyncio.wait_for(pairing.list_accessories_and_characteristics(), 10)
    assert _accessory_signature(accessories) == baseline["accessories_signature"]
    assert sorted(item["aid"] for item in accessories) == baseline["logical"]["aids"]
    await pairing.shutdown()


async def _read_with_pairing(shared: Path, label: str) -> list[dict]:
    pairing = IpPairing(
        Controller(),
        json.loads(
            (shared / f'{label.lower().replace(" ", "_")}.pairing.json').read_text(
                encoding="utf-8"
            )
        ),
    )
    try:
        return await asyncio.wait_for(pairing.list_accessories_and_characteristics(), 10)
    finally:
        await pairing.shutdown()


def _save_baseline(shared: Path, name: str, pairing_data: dict, observed: dict) -> None:
    label = name.lower().replace(" ", "_")
    (shared / f"{label}.pairing.json").write_text(
        json.dumps(pairing_data), encoding="utf-8", errors="strict"
    )
    (shared / f"{label}.pairing.json").chmod(0o600)
    baseline = {
        "logical": observed["logical"],
        "accessories_signature": _accessory_signature(observed["accessories"]),
        "pairing_fingerprint": observed["pairing_fingerprint"],
    }
    (shared / f"{label}.baseline.json").write_text(json.dumps(baseline), encoding="utf-8")


def _load_baseline(shared: Path, name: str) -> dict:
    label = name.lower().replace(" ", "_")
    return json.loads((shared / f"{label}.baseline.json").read_text(encoding="utf-8"))


async def _add_user_entry(hass, *, name: str, entry_id: str, port: int, entity_id: str):
    entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain="homekit",
        title=name,
        data={
            "name": name,
            "port": port,
            "ip_address": "127.0.0.1",
            "advertise_ip": ["127.0.0.1"],
        },
        options={"mode": "bridge", "filter": {"include_entities": [entity_id]}},
        source=config_entries.SOURCE_USER,
        entry_id=entry_id,
        unique_id=None,
        discovery_keys={},
        subentries_data=None,
    )
    await hass.config_entries.async_add(entry)
    return entry


async def _verify_both(shared: Path, hass, expected_a_source: str) -> None:
    entries = await wait_for_entries(
        hass,
        {"Bridge A": expected_a_source, "Bridge B": config_entries.SOURCE_USER},
    )
    assert len(hass.config_entries.async_entries("homekit")) == 2
    assert len([entry for entry in entries.values() if entry.state.value == "loaded"]) == 2

    for name in ("Bridge A", "Bridge B"):
        baseline = _load_baseline(shared, name)
        entry = entries[name]
        current = _logical_identity(entry, await _read_with_pairing(shared, name))
        for key in ("entry_id", "name", "port", "mac", "aids", "iids", "allowlist"):
            assert current[key] == baseline["logical"][key], (name, key, current[key], baseline["logical"][key])
        await _reconnect(shared, name, baseline)

    observation = hass.data.get("homekit_migration", {})
    if observation.get("action") == "manual_recovery":
        # A corrupted request may contain an untrusted entry id.  It must not
        # be interpreted as Bridge B, but the test must not bless it as A.
        assert observation.get("entry_id") != entries["Bridge B"].entry_id
    else:
        assert observation.get("entry_id") in {None, entries["Bridge A"].entry_id}


async def run() -> None:
    shared = Path(os.environ["HKM_CORE_MULTIBRIDGE_DIR"])
    direction = os.environ["HKM_CORE_MULTIBRIDGE_DIRECTION"]
    phase = os.environ["HKM_CORE_MULTIBRIDGE_PHASE"]
    name = "Bridge A"
    yaml_bridge = direction == "yaml_to_ui"
    expected_source_override = os.environ.get("HKM_CORE_MULTIBRIDGE_EXPECT_SOURCE")

    if phase == "pair":
        port_a, port_b = free_loopback_port(), free_loopback_port()
        write_configuration(shared, yaml_bridge=yaml_bridge, name=name, port=port_a)
    else:
        port_a = int(json.loads((shared / "ports.json").read_text(encoding="utf-8"))["a"])
        port_b = int(json.loads((shared / "ports.json").read_text(encoding="utf-8"))["b"])

    with (
        patch("homeassistant.components.homekit.zeroconf.async_get_async_instance", local_advertiser),
        patch.object(HomeKit, "_async_show_setup_message", lambda _self: None),
    ):
        hass = await boot(shared)
        if phase == "pair":
            (shared / "ports.json").write_text(json.dumps({"a": port_a, "b": port_b}), encoding="utf-8")
            await _add_user_entry(
                hass, name="Bridge B", entry_id=ENTRY_B, port=port_b, entity_id=ENTITY_B
            )
            expected = {"Bridge B": config_entries.SOURCE_USER}
            if yaml_bridge:
                expected["Bridge A"] = config_entries.SOURCE_IMPORT
            else:
                await _add_user_entry(
                    hass,
                    name="Bridge A",
                    entry_id="isolated-multi-bridge-a-015",
                    port=port_a,
                    entity_id=ENTITY_A,
                )
                expected["Bridge A"] = config_entries.SOURCE_USER
            await hass.async_start()
            await hass.async_block_till_done()
            entries = await wait_for_entries(hass, expected)
            pairing_a, observed_a = await _pair(entries["Bridge A"], "bridge-a-015")
            pairing_b, observed_b = await _pair(entries["Bridge B"], "bridge-b-015")
            _save_baseline(shared, "Bridge A", pairing_a, observed_a)
            _save_baseline(shared, "Bridge B", pairing_b, observed_b)
            await hass.async_stop(force=True)
            return

        await hass.async_start()
        await hass.async_block_till_done()
        if phase == "verify_corrupt":
            observation = hass.data.get("homekit_migration", {})
            assert observation.get("action") == "manual_recovery", observation
            assert observation.get("state") == "MANUAL_RECOVERY_REQUIRED", observation
        if phase == "migrate":
            entries = await wait_for_entries(
                hass,
                {
                    "Bridge A": config_entries.SOURCE_USER
                    if direction == "ui_to_yaml"
                    else config_entries.SOURCE_IMPORT,
                    "Bridge B": config_entries.SOURCE_USER,
                },
            )
            entry_a = entries["Bridge A"]
            baseline = _load_baseline(shared, "Bridge A")
            await hass.config_entries.async_unload(entry_a.entry_id)
            await hass.async_block_till_done()
            target = (
                config_entries.SOURCE_IMPORT
                if direction == "ui_to_yaml"
                else config_entries.SOURCE_USER
            )
            target_data = {"name": name, "port": entry_a.data["port"]}
            if target == config_entries.SOURCE_IMPORT:
                target_data.update({"ip_address": "127.0.0.1", "advertise_ip": ["127.0.0.1"]})
            request = {
                "schema_version": 1,
                "transaction_id": f"tx-multi-{direction}-015",
                "entry_id": entry_a.entry_id,
                "source": entry_a.source,
                "target": target,
                "state": "PREPARED",
                "name": name,
                "port": entry_a.data["port"],
                "target_data": target_data,
                "target_options": dict(entry_a.options),
                "baseline_fingerprint": "preflight",
                "allowlist": baseline["logical"]["allowlist"],
                "mac": baseline["logical"]["mac"],
            }
            prepared = await async_prepare(hass, request)
            if prepared.get("state") != "PREPARED":
                raise RuntimeError(f"HomeKit migration prepare failed: {prepared!r}")
            if target == config_entries.SOURCE_IMPORT:
                write_configuration(shared, yaml_bridge=True, name=name, port=entry_a.data["port"])
            switched = await async_switch(hass, request["transaction_id"])
            if switched.get("state") != "SOURCE_SWITCHED":
                raise RuntimeError(f"HomeKit migration switch failed: {switched!r}")
            await hass.async_block_till_done()
            (shared / "fault-reached").write_text("AFTER_SOURCE_MUTATION", encoding="utf-8")
            os.kill(os.getpid(), signal.SIGKILL)

        await _verify_both(
            shared,
            hass,
            expected_source_override
            or (
                config_entries.SOURCE_IMPORT
                if direction == "ui_to_yaml"
                else config_entries.SOURCE_USER
            ),
        )
        await hass.async_stop(force=True)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except BaseException as err:
        print(f"WORKER_FAILURE {type(err).__name__}: {err!r}", flush=True)
        traceback.print_exc()
        raise
    gc.freeze()
