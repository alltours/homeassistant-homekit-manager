"""Minimal real-Core YAML HomeKit importer bootstrap worker.

The worker uses Home Assistant's isolated pytest Core lifecycle. It stops
after proving that a SOURCE_IMPORT entry has loaded a real loopback HAP bridge.
It contains no migration or fault logic.
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
from aiohomekit.zeroconf import HomeKitService
from homeassistant import config_entries
from homeassistant.components.homekit import HomeKit
from homeassistant.config import async_hass_config_yaml
from homeassistant.setup import async_setup_component

ENTITY_ID = "input_boolean.yaml_bootstrap_test"


class LocalAdvertiser:
    """Suppress mDNS publication while leaving the HAP TCP server running."""

    async def async_register_service(self, _service, **_kwargs):
        return None

    async def async_unregister_service(self, _service):
        return None

    async def async_update_service(self, _service):
        return None

    async def async_close(self):
        return None


async def _local_advertiser(_hass):
    return LocalAdvertiser()


async def _local_addresses(_hass):
    return ["127.0.0.1"]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]


@pytest.mark.asyncio
async def test_worker(hass, monkeypatch, socket_enabled):
    """Run one bounded, isolated YAML-import bootstrap."""
    shared = Path(os.environ["HKM_YAML_BOOTSTRAP_DIR"])
    shared.mkdir(mode=0o700, parents=True, exist_ok=True)
    port = _free_port()
    (shared / "configuration.yaml").write_text(
        "homeassistant:\n"
        "  name: Isolated YAML Import\n"
        f"homekit:\n"
        f"  - name: YAML Bootstrap Bridge\n"
        f"    port: {port}\n"
        "    ip_address: 127.0.0.1\n"
        "    advertise_ip:\n"
        "      - 127.0.0.1\n"
        "    filter:\n"
        f"      include_entities:\n        - {ENTITY_ID}\n"
        "input_boolean:\n"
        "  yaml_bootstrap_test:\n"
        "    name: YAML Bootstrap Test\n"
        "logger:\n"
        "  default: critical\n",
        encoding="utf-8",
    )
    hass.config.config_dir = str(shared)
    (shared / ".storage").mkdir(mode=0o700, exist_ok=True)
    hass.config_entries = config_entries.ConfigEntries(hass, {"_": "yaml bootstrap"})
    await hass.config_entries.async_initialize()
    hass.states.async_set(ENTITY_ID, "off")
    await hass.async_block_till_done()

    monkeypatch.setattr(
        "homeassistant.components.homekit.zeroconf.async_get_async_instance",
        _local_advertiser,
    )
    monkeypatch.setattr(
        "homeassistant.components.homekit.network.async_get_announce_addresses",
        _local_addresses,
    )
    monkeypatch.setattr(HomeKit, "_async_show_setup_message", lambda _self: None)

    config = await async_hass_config_yaml(hass)
    assert "homekit" in config
    assert await async_setup_component(hass, "homekit", config)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries("homekit")
    assert len(entries) == 1
    entry = entries[0]
    assert entry.source == config_entries.SOURCE_IMPORT
    if entry.state.value != "loaded":
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state.value == "loaded"
    homekit = entry.runtime_data.homekit
    assert homekit.driver is not None and homekit.status == 1
    assert entry.data["port"] == port

    controller = Controller()
    discovery = IpDiscovery(
        controller,
        HomeKitService.from_service_info(homekit.driver.mdns_service_info),
    )
    try:
        finish = await asyncio.wait_for(
            discovery.async_start_pairing("yaml-bootstrap"), timeout=10
        )
        pairing = await asyncio.wait_for(
            finish(homekit.driver.state.pincode.decode()), timeout=10
        )
    finally:
        await discovery.close()
    accessories = await asyncio.wait_for(
        pairing.list_accessories_and_characteristics(), timeout=10
    )
    assert accessories
    (shared / "public_identity.json").write_text(
        json.dumps(
            {
                "entry_id": entry.entry_id,
                "source": entry.source,
                "port": port,
                "mac": homekit.driver.state.mac,
                "aids": sorted(item["aid"] for item in accessories),
            }
        ),
        encoding="utf-8",
    )
    secret = shared / "controller_pairing.json"
    secret.write_text(json.dumps(pairing.pairing_data), encoding="utf-8")
    secret.chmod(0o600)
    await pairing.shutdown()
