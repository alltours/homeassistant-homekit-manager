"""Exercise the native Manager filter writer on isolated Core 2026.11.0b0.

The caller first pairs the loopback HAP bridge with the full-bootstrap worker.
No test mDNS packet or persistence file reaches the productive HA host.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import gc
import json
import os
from pathlib import Path
import traceback
from unittest.mock import patch

from homeassistant.bootstrap import async_setup_hass
from homeassistant.components.homekit import HomeKit
from homeassistant.components.homekit.accessories import TYPES, get_accessory
from homeassistant.const import __version__ as CORE_VERSION
from homeassistant.core import State
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.runner import RuntimeConfig

from custom_components.homekit_manager.operations import HomeKitOperationService
from custom_components.homekit_manager.compatibility import classify_entity


ENTRY_ID = "isolated-hap-full-bootstrap"
SENSORS = (
    "sensor.blaue_tonne", "sensor.braune_tonne",
    "sensor.gelbe_tonne", "sensor.graue_tonne",
)


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


async def run() -> None:
    assert CORE_VERSION == "2026.11.0b0"
    # Probe the installed beta's actual accessory dispatch before reporting
    # support. This does not start a HAP driver or touch the productive host.
    for device_class, accessory_type in (("ozone", "OzoneSensor"), ("sulphur_dioxide", "SulphurDioxideSensor")):
        state = State(f"sensor.beta_{device_class}", "20", {"device_class": device_class})
        with patch.dict(TYPES, {accessory_type: lambda *_args: accessory_type}):
            assert get_accessory(None, None, state, 1, {}) == accessory_type
        projected = classify_entity({"domain": "sensor", "device_class": device_class}, core_version=CORE_VERSION)
        assert projected.status == "supported" and projected.expected_type == accessory_type
    assert classify_entity({"domain": "light"}, core_version=CORE_VERSION).status == "supported"
    shared = Path(os.environ["HKM_FULL_BOOTSTRAP_DIR"])
    assert shared.is_dir() and (shared / "controller_pairing.json").is_file()
    with patch("homeassistant.components.homekit.zeroconf.async_get_async_instance", local_advertiser), patch.object(HomeKit, "_async_show_setup_message", lambda _self: None):
        hass = await async_setup_hass(RuntimeConfig(
            config_dir=str(shared), skip_pip=True,
            log_file=str(shared / "home-assistant.log"),
        ))
        assert hass is not None
        await hass.async_start()
        await hass.async_block_till_done()
        entry = hass.config_entries.async_get_entry(ENTRY_ID)
        assert entry is not None and entry.state.value == "loaded" and entry.source == "user"
        for entity_id in SENSORS:
            hass.states.async_set(entity_id, "20", {
                "device_class": "temperature", "unit_of_measurement": "°C",
            })
        await hass.async_block_till_done()

        # The paired bootstrap bridge has one input_boolean. Add the same
        # sensor-domain rule as the productive bridge in this isolated copy.
        base_options = deepcopy(dict(entry.options))
        base_options["filter"]["include_domains"] = ["sensor"]
        hass.config_entries.async_update_entry(entry, options=base_options)
        await hass.async_block_till_done()
        assert entry.state.value == "loaded"
        before = entry.runtime_data.homekit
        mac = before.driver.state.mac
        aid = before.aid_storage.get_allocated_aid_for_entity_id("input_boolean.restart_test")
        iids = deepcopy(before.iid_storage.allocations.get(aid))
        data = dict(entry.data)
        predicate = FILTER_SCHEMA(base_options["filter"]).get_filter()
        assert all(predicate(entity_id) for entity_id in SENSORS)

        service = HomeKitOperationService(hass)
        bridge = {"entry_id": ENTRY_ID, "source": "user", "filter": dict(entry.options["filter"])}
        inventory = [
            {"entity_id": entity_id, "homekit": {"configured_by_filter": True},
             "compatibility": {"status": "supported"}, "available": True}
            for entity_id in SENSORS
        ]
        inventory.append({"entity_id": "input_boolean.restart_test",
                          "homekit": {"configured_by_filter": True},
                          "compatibility": {"status": "supported"}, "available": True})
        document = {"schema_version": 1, "bridges": {ENTRY_ID: {
            "policy": "explicit_overrides",
            "entities": {entity_id: "exclude" for entity_id in SENSORS},
        }}}
        plan = await service.plan_filter(entry_id=ENTRY_ID, bridge=bridge,
                                         document=document, inventory=inventory)
        assert plan["apply_enabled"] is True
        assert set(plan["changed_entities"]) == set(SENSORS)
        assert not (shared / ".homekit_manager_write_grant.json").exists()
        result = await service.apply(
            plan["operation_id"], entry_id=ENTRY_ID,
            expected_revision=plan["source_revision"],
            confirmed_operation_id=plan["operation_id"], admin=True,
        )
        assert result["state"] == "verified" and result["pairing_verified"] is False
        assert dict(entry.data) == data and entry.options["mode"] == base_options["mode"]
        assert entry.options["filter"]["include_domains"] == ["sensor"]
        assert entry.options["filter"]["exclude_entities"] == sorted(SENSORS)
        after_predicate = FILTER_SCHEMA(entry.options["filter"]).get_filter()
        assert all(not after_predicate(entity_id) for entity_id in SENSORS)
        assert after_predicate("sensor.andere_tonne")
        assert (await service.reconcile(plan["operation_id"]))["state"] == "verified"
        after = entry.runtime_data.homekit
        assert after is not before and after.driver.state.mac == mac and after.driver.state.paired
        assert after.aid_storage.get_allocated_aid_for_entity_id("input_boolean.restart_test") == aid
        assert after.iid_storage.allocations.get(aid) == iids
        assert (await service.authority_status(ENTRY_ID, "user"))["authority"] == "confirmed_operation"
        # Core schedules config-entry persistence after a one-second delay.
        await asyncio.sleep(1.2)
        saved = json.loads((shared / ".storage" / "core.config_entries").read_text())
        saved_entry = next(item for item in saved["data"]["entries"] if item["entry_id"] == ENTRY_ID)
        assert saved_entry["options"]["filter"]["exclude_entities"] == sorted(SENSORS)
        await hass.async_stop(force=True)
    print("Beta native Manager filter Apply, reload and HAP identity verified in isolation")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except BaseException:
        traceback.print_exc()
        raise
    # macOS Python 3.14/Core finalization can crash after clean shutdown.
    gc.freeze()
