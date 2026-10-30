"""Ephemeral native test authority against isolated Home Assistant Core."""
from __future__ import annotations

import asyncio
from dataclasses import replace
import time

import pytest
from homeassistant import config_entries
from homeassistant.helpers import entity_registry as er

from custom_components.homekit_manager import homekit_writer as writer_module
from custom_components.homekit_manager.homekit_writer import HomeKitWriter, OptionsDiff
from custom_components.homekit_manager.operations import HomeKitOperationService
from custom_components.homekit_manager.source_model import native_source
from custom_components.homekit_manager.write_test_mode import (
    TestModeAuthority as ModeAuthority,
    TestModeBlocked as ModeBlocked,
    TestWriteMode as WriteMode,
)


async def native_entry(hass, monkeypatch, *, suffix="test", mode="bridge"):
    async def no_network_start(_self):
        return None

    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    entry = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="Test mode",
        data={"name": "Test mode", "port": 21110},
        options={"mode": mode, "filter": {"include_entities": ["light.before"]}},
        source=config_entries.SOURCE_USER, entry_id=f"test-mode-{suffix}",
        unique_id=None, discovery_keys={}, subentries_data=None,
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    return entry


def desired(entry_id):
    return {"schema_version": 1, "bridges": {entry_id: {
        "policy": "explicit_overrides", "entities": {"light.after": "include"}}}}


def inventory():
    return [{"entity_id": name, "homekit": {"configured_by_filter": name == "light.before"},
             "compatibility": {"status": "supported"}, "registry_entry_present": True, "state_present": True}
            for name in ("light.before", "light.after")]


async def test_native_test_mode_requires_exact_bridge_and_expires_without_file(hass, monkeypatch):
    entry = await native_entry(hass, monkeypatch)
    mode = WriteMode()
    assert mode.status()["enabled"] is False
    with pytest.raises(ModeBlocked, match="Bridge-ID"):
        mode.enable(hass, entry.entry_id, "other")
    authority = mode.enable(hass, entry.entry_id, entry.entry_id)
    assert mode.status(entry.entry_id)["enabled"] is True
    assert mode.status()["persistent"] is False
    await authority.verify(hass, entry.entry_id, "user")
    with pytest.raises(ModeBlocked):
        await authority.verify(hass, "other", "user")
    assert WriteMode().status()["enabled"] is False  # Core restart/new service
    mode._authority = replace(authority, deadline=time.monotonic() - 1)
    assert mode.status()["enabled"] is False
    with pytest.raises(ModeBlocked):
        await authority.verify(hass, entry.entry_id, "user")


async def test_removed_bridge_invalidates_active_test_mode(hass, monkeypatch):
    entry = await native_entry(hass, monkeypatch, suffix="removed")
    mode = WriteMode()
    authority = mode.enable(hass, entry.entry_id, entry.entry_id)
    await hass.config_entries.async_remove(entry.entry_id)
    with pytest.raises(ModeBlocked, match="Bridge"):
        await authority.verify(hass, entry.entry_id, "user")


async def test_native_test_mode_applies_filter_once_and_revokes(hass, monkeypatch):
    entry = await native_entry(hass, monkeypatch, suffix="apply")
    service = HomeKitOperationService(hass)
    bridge = {"entry_id": entry.entry_id, "source": "user", "filter": dict(entry.options["filter"])}
    assert (await service.authority_status(entry.entry_id, "user"))["enabled"] is False
    service.test_write_mode.enable(hass, entry.entry_id, entry.entry_id)
    plan = await service.plan_filter(entry_id=entry.entry_id, bridge=bridge,
                                     document=desired(entry.entry_id), inventory=inventory())
    assert plan["apply_enabled"] is True
    assert (await service.authority_status(entry.entry_id, "user"))["authority"] == "test_mode"
    args = {"entry_id": entry.entry_id, "expected_revision": plan["source_revision"],
            "confirmed_operation_id": plan["operation_id"], "admin": True}
    service.test_write_mode.disable()
    with pytest.raises(Exception, match="Schreibfreigabe"):
        await service.apply(plan["operation_id"], **args)
    service.test_write_mode.enable(hass, entry.entry_id, entry.entry_id)
    with pytest.raises(Exception, match="seit der Vorschau"):
        await service.apply(plan["operation_id"], **args)
    plan = await service.plan_filter(entry_id=entry.entry_id, bridge=bridge,
                                     document=desired(entry.entry_id), inventory=inventory())
    args = {"entry_id": entry.entry_id, "expected_revision": plan["source_revision"],
            "confirmed_operation_id": plan["operation_id"], "admin": True}
    with pytest.raises(Exception, match="Bestätigung"):
        await service.apply(plan["operation_id"], **(args | {"confirmed_operation_id": "wrong"}))
    result = await service.apply(plan["operation_id"], **args)
    assert result["state"] == "verified"
    assert entry.options["filter"]["include_entities"] == ["light.after", "light.before"]
    assert (await service.reconcile(plan["operation_id"]))["state"] == "verified"
    service.test_write_mode.disable()
    assert (await service.authority_status(entry.entry_id, "user"))["enabled"] is False
    assert WriteMode().status()["enabled"] is False


async def test_revocation_while_waiting_for_native_lock_prevents_mutation(hass, monkeypatch):
    entry = await native_entry(hass, monkeypatch, suffix="revoke")
    service = HomeKitOperationService(hass)
    authority = service.test_write_mode.enable(hass, entry.entry_id, entry.entry_id)
    before = dict(entry.options["filter"])
    diff = OptionsDiff(entry.entry_id, {"filter": before},
                       {"filter": {"include_entities": ["light.after"]}},
                       ("filter",), ("light.after",), {"summary": {"blocked": False}})
    lock = writer_module._locks.setdefault(entry.entry_id, asyncio.Lock())
    first_check = asyncio.Event()
    original_verify = ModeAuthority.verify

    async def observe_verify(self, *args):
        await original_verify(self, *args)
        first_check.set()

    monkeypatch.setattr(ModeAuthority, "verify", observe_verify)
    await lock.acquire()
    task = asyncio.create_task(HomeKitWriter(hass, production_grant=authority,
                                            expected_source_revision=native_source(entry, "2026.10.4").revision).async_apply(diff))
    await asyncio.wait_for(first_check.wait(), 5)
    service.test_write_mode.disable()
    lock.release()
    with pytest.raises(ModeBlocked):
        await task
    assert entry.options["filter"] == before


async def test_test_mode_blocks_wrong_core_and_accessory(hass, monkeypatch):
    entry = await native_entry(hass, monkeypatch, suffix="version")
    mode = WriteMode()
    with monkeypatch.context() as patcher:
        patcher.setattr("homeassistant.const.__version__", "2026.12.0")
        with pytest.raises(ModeBlocked, match="Core-Version"):
            mode.enable(hass, entry.entry_id, entry.entry_id)
    accessory = await native_entry(hass, monkeypatch, suffix="accessory", mode="accessory")
    with pytest.raises(ModeBlocked, match="Bridge-Modus"):
        mode.enable(hass, accessory.entry_id, accessory.entry_id)


async def test_admin_websocket_test_mode_without_grant_file(hass, monkeypatch,
                                                           enable_custom_integrations, hass_ws_client):
    entry = await native_entry(hass, monkeypatch, suffix="websocket")
    hass.states.async_set("light.before", "on")
    assert er.async_get(hass).async_get_or_create("light", "test", "after", suggested_object_id="after").entity_id == "light.after"
    hass.states.async_set("light.after", "on")
    flow = await hass.config_entries.flow.async_init("homekit_manager", context={"source": "user"})
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    manager = hass.data["homekit_manager"]["coordinator"]
    assert manager.selected_bridge_id == entry.entry_id
    client = await hass_ws_client()
    command = {"type": "homekit_manager/test_write_mode_enable", "entry_id": entry.entry_id,
               "expected_fingerprint": manager.fingerprint, "confirmed_entry_id": "wrong"}
    await client.send_json_auto_id(command)
    assert (await client.receive_json())["success"] is False
    assert manager.operation_service.test_write_mode.status()["enabled"] is False
    await client.send_json_auto_id(command | {"confirmed_entry_id": entry.entry_id})
    enabled = await client.receive_json()
    assert enabled["success"] and enabled["result"]["persistent"] is False
    assert manager.operation_policy["authority"] == "test_mode"
    await client.send_json_auto_id({"type": "homekit_manager/operation_plan", "entry_id": entry.entry_id,
                                    "document": desired(entry.entry_id),
                                    "expected_fingerprint": manager.fingerprint})
    planned = await client.receive_json()
    assert planned["success"] and planned["result"]["apply_enabled"] is True
    plan = planned["result"]
    await client.send_json_auto_id({"type": "homekit_manager/operation_apply",
                                    "operation_id": plan["operation_id"], "entry_id": entry.entry_id,
                                    "source_revision": plan["source_revision"],
                                    "expected_fingerprint": manager.fingerprint,
                                    "confirmed_operation_id": plan["operation_id"]})
    applied = await client.receive_json()
    assert applied["success"] and applied["result"]["state"] == "verified"
    assert entry.options["filter"]["include_entities"] == ["light.after", "light.before"]
    await client.send_json_auto_id({"type": "homekit_manager/test_write_mode_disable"})
    disabled = await client.receive_json()
    assert disabled["success"] and disabled["result"]["enabled"] is False
    assert manager.operation_service.test_write_mode.status()["enabled"] is False
