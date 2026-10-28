"""Exercise local production authority only in isolated Core fixtures."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from uuid import uuid4

import pytest
from homeassistant import config_entries
from homeassistant.config import async_hass_config_yaml
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homekit_manager import homekit_writer as writer_module
from custom_components.homekit_manager.homekit_writer import HomeKitWriteBlocked, HomeKitWriteDisabled, HomeKitWriter, OptionsDiff
from custom_components.homekit_manager.operations import HomeKitOperationService
from custom_components.homekit_manager.write_grant import GRANT_FILENAME, GrantBlocked, ProductionWriteGrant, read_production_grant
from custom_components.homekit_manager.yaml_adapter import YamlHomeKitAdapter


def grant_data(entry_id: str, source: str = "user") -> dict:
    now = datetime.now(timezone.utc)
    return {"version": 1, "grant_id": uuid4().hex, "entry_id": entry_id, "source": source,
            "core_version": "2026.10.4", "allowed_fields": ["filter"],
            "issued_at": (now - timedelta(minutes=1)).isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat()}


def save_grant(tmp_path, data: dict) -> None:
    path = tmp_path / GRANT_FILENAME
    path.write_text(json.dumps(data))
    path.chmod(0o600)


def desired(entry_id: str) -> dict:
    return {"schema_version": 1, "bridges": {entry_id: {
        "policy": "explicit_overrides", "entities": {"light.after": "include"}}}}


def inventory() -> list[dict]:
    return [{"entity_id": name, "homekit": {"configured_by_filter": name == "light.before"},
             "compatibility": {"status": "supported"}} for name in ("light.before", "light.after")]


@pytest.mark.parametrize("change", [
    lambda data: data.update(allowed_fields=["filter", "mode"]),
    lambda data: data.update(entry_id=""),
    lambda data: data.update(source="system"),
    lambda data: data.update(core_version="2026.11.0"),
    lambda data: data.update(expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()),
    lambda data: data.update(expires_at=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat()),
    lambda data: data.update(unrecognized=True),
])
async def test_invalid_local_grants_fail_closed(hass, tmp_path, change):
    data = grant_data("isolated-entry")
    change(data)
    save_grant(tmp_path, data)
    with pytest.raises(GrantBlocked):
        await read_production_grant(hass)


async def test_grant_file_permissions_and_symlink_fail_closed(hass, tmp_path):
    assert await read_production_grant(hass) is None
    save_grant(tmp_path, grant_data("isolated-entry"))
    path = tmp_path / GRANT_FILENAME
    path.chmod(0o644)
    with pytest.raises(GrantBlocked, match="0600"):
        await read_production_grant(hass)
    path.unlink()
    target = tmp_path / "other.json"
    target.write_text(json.dumps(grant_data("isolated-entry")))
    target.chmod(0o600)
    path.symlink_to(target)
    with pytest.raises(GrantBlocked):
        await read_production_grant(hass)
    path.unlink()
    os.mkfifo(path, mode=0o600)
    with pytest.raises(GrantBlocked, match="reguläre Datei"):
        await read_production_grant(hass)
    path.unlink()
    save_grant(tmp_path, grant_data("isolated-entry"))
    assert (await read_production_grant(hass)).entry_id == "isolated-entry"
    original_mode = tmp_path.stat().st_mode & 0o777
    tmp_path.chmod(0o777)
    try:
        with pytest.raises(GrantBlocked, match="Verzeichnis"):
            await read_production_grant(hass)
    finally:
        tmp_path.chmod(original_mode)
    os.link(path, tmp_path / "second-link.json")
    with pytest.raises(GrantBlocked, match="0600"):
        await read_production_grant(hass)


async def test_duplicate_grant_fields_and_writer_time_revocation(hass, tmp_path):
    path = tmp_path / GRANT_FILENAME
    path.write_text('{"version":1,"version":1}')
    path.chmod(0o600)
    with pytest.raises(GrantBlocked, match="Doppeltes Feld"):
        await read_production_grant(hass)
    path.unlink()
    save_grant(tmp_path, grant_data("isolated-entry"))
    grant = await read_production_grant(hass)
    path.unlink()
    diff = OptionsDiff("isolated-entry", {"filter": {}}, {"filter": {"include_entities": ["light.after"]}},
                       ("filter",), ("light.after",), {"summary": {"blocked": False}})
    with pytest.raises(GrantBlocked, match="widerrufen"):
        await HomeKitWriter(hass, production_grant=grant).async_apply(diff)


async def test_replacing_grant_with_identical_bytes_revokes_existing_plan(hass, tmp_path):
    save_grant(tmp_path, grant_data("isolated-entry"))
    path = tmp_path / GRANT_FILENAME
    grant = await read_production_grant(hass)
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(path.read_bytes())
    replacement.chmod(0o600)
    os.replace(replacement, path)
    with pytest.raises(GrantBlocked, match="widerrufen"):
        await grant.verify(hass, "isolated-entry", "user")


async def test_native_grant_revoked_while_waiting_for_bridge_lock(hass, tmp_path, monkeypatch):
    entry = MockConfigEntry(domain="homekit", entry_id="isolated-lock-revocation", source="user",
                            data={"name": "Lock test", "port": 21096},
                            options={"mode": "bridge", "filter": {"include_entities": ["light.before"]}})
    entry.add_to_hass(hass)
    save_grant(tmp_path, grant_data(entry.entry_id))
    grant = await read_production_grant(hass)
    before = dict(entry.options["filter"])
    diff = OptionsDiff(entry.entry_id, {"filter": before},
                       {"filter": {"include_entities": ["light.after"]}},
                       ("filter",), ("light.after",), {"summary": {"blocked": False}})
    first_check = asyncio.Event()
    original_verify = ProductionWriteGrant.verify

    async def observe_verify(self, *args):
        await original_verify(self, *args)
        first_check.set()

    monkeypatch.setattr(ProductionWriteGrant, "verify", observe_verify)
    lock = writer_module._locks.setdefault(entry.entry_id, asyncio.Lock())
    await lock.acquire()
    task = asyncio.create_task(HomeKitWriter(hass, production_grant=grant).async_apply(diff))
    try:
        await asyncio.wait_for(first_check.wait(), 5)
        (tmp_path / GRANT_FILENAME).unlink()
    finally:
        lock.release()
    with pytest.raises(GrantBlocked, match="widerrufen"):
        await task
    assert entry.options["filter"] == before


async def test_native_grant_is_bound_revocable_and_single_use(hass, tmp_path, monkeypatch):
    async def no_network_start(_self):
        return None
    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    entry = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="Grant Native",
        data={"name": "Grant Native", "port": 21092},
        options={"mode": "bridge", "filter": {"include_entities": ["light.before"]}},
        source=config_entries.SOURCE_USER, entry_id="grant-native", unique_id=None,
        discovery_keys={}, subentries_data=None,
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    bridge = {"entry_id": entry.entry_id, "source": "user", "filter": dict(entry.options["filter"])}
    service = HomeKitOperationService(hass)
    save_grant(tmp_path, grant_data(entry.entry_id, "import"))
    assert (await service.authority_status(entry.entry_id, "user"))["enabled"] is False
    save_grant(tmp_path, grant_data(entry.entry_id))
    plan = await service.plan_filter(entry_id=entry.entry_id, bridge=bridge,
                                     document=desired(entry.entry_id), inventory=inventory())
    assert plan["apply_enabled"] is True
    args = {"entry_id": entry.entry_id, "expected_revision": plan["source_revision"],
            "confirmed_operation_id": plan["operation_id"], "admin": True}
    (tmp_path / GRANT_FILENAME).unlink()
    with pytest.raises(HomeKitWriteDisabled):
        await service.apply(plan["operation_id"], **args)
    assert entry.options["filter"]["include_entities"] == ["light.before"]
    save_grant(tmp_path, grant_data(entry.entry_id))
    result = await service.apply(plan["operation_id"], **args)
    assert result["state"] == "verified"
    assert entry.options["filter"]["include_entities"] == ["light.after", "light.before"]
    with pytest.raises(HomeKitWriteBlocked, match="bereits begonnen"):
        await service.apply(plan["operation_id"], **args)


async def test_yaml_grant_applies_only_to_isolated_import(hass, tmp_path, monkeypatch):
    async def no_network_start(_self):
        return None
    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    (tmp_path / "configuration.yaml").write_text("homekit: !include grant_bridges.yaml\n")
    source = tmp_path / "grant_bridges.yaml"
    source.write_text("- name: Grant YAML\n  port: 21093\n  filter:\n    include_entities:\n    - light.before\n")
    assert await async_setup_component(hass, "homekit", await async_hass_config_yaml(hass))
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries("homekit")[0]
    save_grant(tmp_path, grant_data(entry.entry_id, "import"))
    adapter = YamlHomeKitAdapter(tmp_path)
    queued_plan = adapter.plan_filter(entry, {"include_entities": ["light.before", "light.after"]})
    queued_grant = await read_production_grant(hass)
    before = source.read_bytes()
    original_executor = hass.async_add_executor_job

    async def revoke_before_queued_write(job, *args):
        if getattr(job, "__name__", "") == "write_with_grant_check":
            (tmp_path / GRANT_FILENAME).unlink()
        return await original_executor(job, *args)

    monkeypatch.setattr(hass, "async_add_executor_job", revoke_before_queued_write)
    with pytest.raises(GrantBlocked, match="widerrufen"):
        await adapter.async_apply_with_core(hass, entry, queued_plan, production_grant=queued_grant)
    assert source.read_bytes() == before
    monkeypatch.setattr(hass, "async_add_executor_job", original_executor)
    save_grant(tmp_path, grant_data(entry.entry_id, "import"))
    service = HomeKitOperationService(hass)
    bridge = {"entry_id": entry.entry_id, "source": "import", "filter": dict(entry.options["filter"])}
    plan = await service.plan_filter(entry_id=entry.entry_id, bridge=bridge,
                                     document=desired(entry.entry_id), inventory=inventory())
    assert plan["apply_enabled"] is True
    result = await service.apply(plan["operation_id"], entry_id=entry.entry_id,
                                 expected_revision=plan["source_revision"],
                                 confirmed_operation_id=plan["operation_id"], admin=True)
    assert result["state"] == "verified"
    assert b"light.after" in source.read_bytes()
    assert (tmp_path / ".storage" / "homekit_manager_backups" / f"{plan['operation_id']}.yaml").is_file()


async def test_real_admin_websocket_uses_local_grant_without_service_injection(
    hass, tmp_path, monkeypatch, enable_custom_integrations, hass_ws_client,
):
    async def no_network_start(_self):
        return None
    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    entry = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="Grant WebSocket",
        data={"name": "Grant WebSocket", "port": 21094},
        options={"mode": "bridge", "filter": {"include_entities": ["light.before"]}},
        source=config_entries.SOURCE_USER, entry_id="grant-websocket", unique_id=None,
        discovery_keys={}, subentries_data=None,
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    hass.states.async_set("light.before", "on")
    hass.states.async_set("light.after", "off")
    flow = await hass.config_entries.flow.async_init("homekit_manager", context={"source": "user"})
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    manager = hass.data["homekit_manager"]["coordinator"]
    assert manager.operation_service._isolated_write_authority is False
    save_grant(tmp_path, grant_data(entry.entry_id))
    await manager.async_refresh()
    assert manager.overview()["operation_policy"]["enabled"] is True
    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "homekit_manager/operation_plan", "entry_id": entry.entry_id,
                                    "document": desired(entry.entry_id), "expected_fingerprint": manager.fingerprint})
    preview = await client.receive_json()
    assert preview["success"], preview
    plan = preview["result"]
    assert plan["apply_enabled"] is True
    (tmp_path / GRANT_FILENAME).unlink()
    await client.send_json_auto_id({"type": "homekit_manager/operation_apply", "operation_id": plan["operation_id"],
                                    "entry_id": entry.entry_id, "source_revision": plan["source_revision"],
                                    "expected_fingerprint": manager.fingerprint,
                                    "confirmed_operation_id": plan["operation_id"]})
    blocked = await client.receive_json()
    assert blocked["success"] is False and blocked["error"]["code"] == "write_blocked"
    assert entry.options["filter"]["include_entities"] == ["light.before"]
    save_grant(tmp_path, grant_data(entry.entry_id))
    await client.send_json_auto_id({"type": "homekit_manager/operation_apply", "operation_id": plan["operation_id"],
                                    "entry_id": entry.entry_id, "source_revision": plan["source_revision"],
                                    "expected_fingerprint": manager.fingerprint,
                                    "confirmed_operation_id": plan["operation_id"]})
    applied = await client.receive_json()
    assert applied["success"] and applied["result"]["state"] == "verified", applied
    assert entry.options["filter"]["include_entities"] == ["light.after", "light.before"]
