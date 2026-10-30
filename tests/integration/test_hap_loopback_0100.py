"""Run Core's real HAP TCP server on loopback with mDNS kept local to the test."""

import asyncio
import socket
from pathlib import Path

from aiohomekit.controller.controller import Controller
from aiohomekit.controller.ip.discovery import IpDiscovery
from aiohomekit.controller.ip.pairing import IpPairing
from aiohomekit.zeroconf import HomeKitService
from homeassistant import config_entries
import pytest

from custom_components.homekit_manager.homekit_writer import HomeKitWriteBlocked, HomeKitWriter, OptionsDiff
from custom_components.homekit_manager.operations import HomeKitOperationService
from custom_components.homekit_manager.filtering import evaluate_filter


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
    """Use actual files in this isolated HA config directory."""
    return {}


async def test_loopback_hap_server_survives_native_filter_reload(hass, monkeypatch, socket_enabled):
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
    await first.aid_storage.async_save()
    await first.iid_storage.async_save()
    assert Path(hass.config.path(".storage", get_aid_storage_filename_for_entry_id(entry.entry_id))).is_file()
    assert Path(hass.config.path(".storage", get_iid_storage_filename_for_entry_id(entry.entry_id))).is_file()

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /accessories HTTP/1.1\r\nHost: localhost\r\n\r\n")
    await writer.drain()
    response = await asyncio.wait_for(reader.read(128), 3)
    writer.close()
    await writer.wait_closed()
    assert response.startswith(b"HTTP/1.1")
    controller = Controller()
    discovery = IpDiscovery(controller, HomeKitService.from_service_info(first.driver.mdns_service_info))
    try:
        finish_pairing = await asyncio.wait_for(discovery.async_start_pairing("isolated"), 10)
        pairing = await asyncio.wait_for(finish_pairing(first.driver.state.pincode.decode()), 10)
    finally:
        await discovery.close()
    await hass.async_add_executor_job(first.driver.persist)
    before_accessories = await asyncio.wait_for(pairing.list_accessories_and_characteristics(), 10)
    assert any(item["aid"] == before_aid for item in before_accessories)
    before_accessory = next(item for item in before_accessories if item["aid"] == before_aid)
    before_iids = sorted(
        iid for service in before_accessory["services"]
        for iid in [service["iid"], *(char["iid"] for char in service["characteristics"])]
    )
    pairing_data = dict(pairing.pairing_data)
    await pairing.shutdown()

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
    after_aid = second.aid_storage.get_allocated_aid_for_entity_id("light.after")
    assert after_aid is not None and after_aid != before_aid
    assert second.driver.state.paired
    reopened_pairing = IpPairing(controller, pairing_data)
    after_accessories = await asyncio.wait_for(reopened_pairing.list_accessories_and_characteristics(), 10)
    assert {item["aid"] for item in after_accessories} >= {before_aid, after_aid}
    after_accessory = next(item for item in after_accessories if item["aid"] == before_aid)
    after_iids = sorted(
        iid for service in after_accessory["services"]
        for iid in [service["iid"], *(char["iid"] for char in service["characteristics"])]
    )
    assert after_iids == before_iids
    await reopened_pairing.shutdown()
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /accessories HTTP/1.1\r\nHost: localhost\r\n\r\n")
    await writer.drain()
    assert (await asyncio.wait_for(reader.read(128), 3)).startswith(b"HTTP/1.1")
    writer.close()
    await writer.wait_closed()


async def test_broad_filter_migration_needs_live_hap_evidence_and_keeps_identity(
    hass, monkeypatch, socket_enabled,
):
    """Use a real loopback Core/HAP bridge; no test mDNS reaches the LAN."""
    from homeassistant.components.homekit import HomeKit
    from homeassistant.helpers import entity_registry as er

    async def local_advertiser(_hass):
        return LocalAdvertiser()

    monkeypatch.setattr("homeassistant.components.homekit.zeroconf.async_get_async_instance", local_advertiser)
    monkeypatch.setattr(HomeKit, "_async_show_setup_message", lambda _self: None)
    Path(hass.config.path(".storage")).mkdir(mode=0o700, exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    for name in ("light.keep", "light.remove"):
        hass.states.async_set(name, "on")
    registry = er.async_get(hass)
    hidden = registry.async_get_or_create("light", "hkm_test", "hidden", suggested_object_id="hidden")
    registry.async_update_entity(hidden.entity_id, hidden_by=er.RegistryEntryHider.USER)
    hass.states.async_set(hidden.entity_id, "on")
    await hass.async_block_till_done()
    entry = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="Migration HAP",
        data={"name": "Migration HAP", "port": port, "ip_address": "127.0.0.1",
              "advertise_ip": ["127.0.0.1"]},
        options={"mode": "bridge", "filter": {"include_domains": ["light"]}},
        source=config_entries.SOURCE_USER, entry_id="isolated-hap-migration",
        unique_id=None, discovery_keys={}, subentries_data=None,
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    assert entry.state.value == "loaded"
    before = entry.runtime_data.homekit
    mac = before.driver.state.mac
    keep_aid = before.aid_storage.get_allocated_aid_for_entity_id("light.keep")
    assert keep_aid in before.bridge.accessories
    controller = Controller()
    discovery = IpDiscovery(controller, HomeKitService.from_service_info(before.driver.mdns_service_info))
    try:
        finish_pairing = await asyncio.wait_for(discovery.async_start_pairing("migration"), 10)
        pairing = await asyncio.wait_for(finish_pairing(before.driver.state.pincode.decode()), 10)
    finally:
        await discovery.close()
    await hass.async_add_executor_job(before.driver.persist)
    pairing_data = dict(pairing.pairing_data)
    await pairing.shutdown()
    assert before.driver.state.paired
    service = HomeKitOperationService(hass)
    service.test_write_mode.enable(hass, entry.entry_id, entry.entry_id)
    bridge = {"entry_id": entry.entry_id, "source": "user", "filter": dict(entry.options["filter"])}
    inventory = [{"entity_id": name, "available": True,
                  "compatibility": {"status": "supported"},
                  "homekit": {"configured_by_filter": evaluate_filter(name, config=bridge["filter"]).configured}}
                 for name in ("light.keep", "light.remove", hidden.entity_id)]
    document = {"schema_version": 1, "bridges": {entry.entry_id: {
        "policy": "positive_list", "migration_acknowledged": True,
        "entities": {"light.keep": "include"},
    }}}
    unsafe = {"schema_version": 1, "bridges": {entry.entry_id: {
        "policy": "positive_list", "migration_acknowledged": True,
        "entities": {"light.keep": "include", hidden.entity_id: "include"},
    }}}
    with pytest.raises(HomeKitWriteBlocked, match="ausgeblendete"):
        await service.plan_filter(entry_id=entry.entry_id, bridge=bridge,
                                  document=unsafe, inventory=inventory)
    plan = await service.plan_filter(entry_id=entry.entry_id, bridge=bridge,
                                     document=document, inventory=inventory)
    assert plan["migration"]["selected_before"] == 3
    assert plan["migration"]["hap_published_before"] == 2
    assert plan["migration"]["published_removals"] == ["light.remove"]
    assert plan["changed_entities"] == [hidden.entity_id, "light.remove"]
    hass.states.async_set("sensor.drift", "1")
    await hass.async_block_till_done()
    with pytest.raises(ValueError, match="Inventar enthält nicht alle"):
        await service.apply(plan["operation_id"], entry_id=entry.entry_id,
                            expected_revision=plan["source_revision"],
                            confirmed_operation_id=plan["operation_id"], admin=True)
    assert entry.options["filter"] == {"include_domains": ["light"]}
    assert (await service.reconcile(plan["operation_id"]))["state"] == "not_applied"
    hass.states.async_remove("sensor.drift")
    await hass.async_block_till_done()
    plan = await service.plan_filter(entry_id=entry.entry_id, bridge=bridge,
                                     document=document, inventory=inventory)
    result = await service.apply(plan["operation_id"], entry_id=entry.entry_id,
                                 expected_revision=plan["source_revision"],
                                 confirmed_operation_id=plan["operation_id"], admin=True)
    assert result["state"] == "verified"
    after = entry.runtime_data.homekit
    assert after.driver.state.mac == mac
    assert after.aid_storage.get_allocated_aid_for_entity_id("light.keep") == keep_aid
    assert after.driver.state.paired
    assert entry.options["filter"] == {"include_entities": ["light.keep"]}
    assert evaluate_filter("light.future", config=entry.options["filter"]).configured is False
    reopened = IpPairing(controller, pairing_data)
    accessories = await asyncio.wait_for(reopened.list_accessories_and_characteristics(), 10)
    assert keep_aid in {accessory["aid"] for accessory in accessories}
    await reopened.shutdown()
