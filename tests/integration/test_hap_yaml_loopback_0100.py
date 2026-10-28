"""Pair a local HAP controller to an imported YAML bridge across Core reload."""
from __future__ import annotations

import asyncio
from pathlib import Path
import socket

from aiohomekit.controller.controller import Controller
from aiohomekit.controller.ip.discovery import IpDiscovery
from aiohomekit.controller.ip.pairing import IpPairing
from aiohomekit.zeroconf import HomeKitService
from homeassistant.config import async_hass_config_yaml
from homeassistant.setup import async_setup_component
import pytest

from custom_components.homekit_manager.operations import HomeKitOperationService


class LocalAdvertiser:
    def __init__(self):
        self.registered = 0
        self.unregistered = 0

    async def async_register_service(self, _service, **_kwargs):
        self.registered += 1

    async def async_unregister_service(self, _service):
        self.unregistered += 1

    async def async_update_service(self, _service):
        return None

    async def async_close(self):
        return None


@pytest.fixture
def hass_storage():
    return {}


async def test_yaml_filter_reload_retains_local_hap_pairing_and_ids(hass, tmp_path, monkeypatch, socket_enabled):
    from homeassistant.components.homekit import HomeKit
    from homeassistant.components.homekit.util import (
        get_aid_storage_filename_for_entry_id,
        get_iid_storage_filename_for_entry_id,
        get_persist_fullpath_for_entry_id,
    )

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
    (tmp_path / "configuration.yaml").write_text("homekit: !include hap_bridges.yaml\n")
    source = tmp_path / "hap_bridges.yaml"
    source.write_text(
        f"- name: YAML HAP\n  port: {port}\n  ip_address: 127.0.0.1\n"
        "  advertise_ip:\n  - 127.0.0.1\n  filter:\n    include_entities:\n    - light.before\n"
    )
    assert await async_setup_component(hass, "homekit", await async_hass_config_yaml(hass))
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries("homekit")[0]
    assert entry.source == "import" and entry.state.value == "loaded"
    first = entry.runtime_data.homekit
    assert first.driver is not None and first.status == 1
    mac = first.driver.state.mac
    before_aid = first.aid_storage.get_allocated_aid_for_entity_id("light.before")
    assert before_aid is not None
    await first.aid_storage.async_save()
    await first.iid_storage.async_save()
    assert Path(get_persist_fullpath_for_entry_id(hass, entry.entry_id)).is_file()
    assert Path(hass.config.path(".storage", get_aid_storage_filename_for_entry_id(entry.entry_id))).is_file()
    assert Path(hass.config.path(".storage", get_iid_storage_filename_for_entry_id(entry.entry_id))).is_file()

    controller = Controller()
    discovery = IpDiscovery(controller, HomeKitService.from_service_info(first.driver.mdns_service_info))
    finish_pairing = await asyncio.wait_for(discovery.async_start_pairing("isolated-yaml"), 10)
    pairing = await asyncio.wait_for(finish_pairing(first.driver.state.pincode.decode()), 10)
    await hass.async_add_executor_job(first.driver.persist)
    before_accessories = await asyncio.wait_for(pairing.list_accessories_and_characteristics(), 10)
    before_accessory = next(item for item in before_accessories if item["aid"] == before_aid)
    before_iids = sorted(
        iid for service in before_accessory["services"]
        for iid in [service["iid"], *(char["iid"] for char in service["characteristics"])]
    )
    pairing_data = dict(pairing.pairing_data)
    await pairing.shutdown()

    service = HomeKitOperationService(hass, isolated_write_authority=True)
    bridge = {"entry_id": entry.entry_id, "source": "import", "filter": dict(entry.options["filter"])}
    document = {"schema_version": 1, "bridges": {entry.entry_id: {
        "policy": "explicit_overrides", "entities": {"light.after": "include"}}}}
    inventory = [{"entity_id": name, "homekit": {"configured_by_filter": name == "light.before"},
                  "compatibility": {"status": "supported"}} for name in ("light.before", "light.after")]
    plan = await service.plan_filter(entry_id=entry.entry_id, bridge=bridge, document=document, inventory=inventory)
    assert (await service.apply(plan["operation_id"], entry_id=entry.entry_id,
                                expected_revision=plan["source_revision"],
                                confirmed_operation_id=plan["operation_id"], admin=True))["state"] == "verified"
    second_entry = hass.config_entries.async_get_entry(entry.entry_id)
    second = second_entry.runtime_data.homekit
    assert second is not first and second.status == 1
    assert advertiser.registered == 2 and advertiser.unregistered == 1
    assert second.driver.state.mac == mac
    assert second.aid_storage.get_allocated_aid_for_entity_id("light.before") == before_aid
    after_aid = second.aid_storage.get_allocated_aid_for_entity_id("light.after")
    assert after_aid is not None and after_aid != before_aid
    assert second.driver.state.paired
    reopened = IpPairing(controller, pairing_data)
    after_accessories = await asyncio.wait_for(reopened.list_accessories_and_characteristics(), 10)
    after_accessory = next(item for item in after_accessories if item["aid"] == before_aid)
    after_iids = sorted(
        iid for item in after_accessory["services"]
        for iid in [item["iid"], *(char["iid"] for char in item["characteristics"])]
    )
    assert after_iids == before_iids
    assert {item["aid"] for item in after_accessories} >= {before_aid, after_aid}
    await reopened.shutdown()
