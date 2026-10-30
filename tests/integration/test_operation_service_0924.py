"""Common operation lifecycle against real isolated Core entries."""
import asyncio
import pytest
from homeassistant import config_entries
from homeassistant.config import async_hass_config_yaml
from homeassistant.setup import async_setup_component

from custom_components.homekit_manager.homekit_writer import HomeKitWriteBlocked, HomeKitWriteDisabled
from custom_components.homekit_manager.operations import HomeKitOperationService
from custom_components.homekit_manager.native_adapter import NativeHomeKitAdapter


def desired(entry_id):
    return {"schema_version": 1, "bridges": {entry_id: {"policy": "explicit_overrides", "entities": {"light.after": "include"}}}}


def inventory():
    return [
        {"entity_id": "light.before", "homekit": {"configured_by_filter": True}, "compatibility": {"status": "supported"}, "registry_entry_present": True, "state_present": True},
        {"entity_id": "light.after", "homekit": {"configured_by_filter": False}, "compatibility": {"status": "supported"}, "registry_entry_present": True, "state_present": True},
    ]


async def test_native_operation_requires_backend_gate_admin_and_exact_confirmation(hass, monkeypatch):
    async def no_network_start(_self):
        return None
    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    entry = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="Operation Native",
        data={"name": "Operation Native", "port": 21082},
        options={"mode": "bridge", "filter": {"include_entities": ["light.before"]}},
        source=config_entries.SOURCE_USER, entry_id="operation-native", unique_id=None,
        discovery_keys={}, subentries_data=None,
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    bridge = {"entry_id": entry.entry_id, "source": "user", "filter": dict(entry.options["filter"])}
    standard = HomeKitOperationService(hass)
    preview = await standard.plan_filter(entry_id=entry.entry_id, bridge=bridge, document=desired(entry.entry_id), inventory=inventory())
    assert preview["apply_enabled"] is False
    with pytest.raises(HomeKitWriteBlocked):
        await standard.apply(preview["operation_id"], entry_id=entry.entry_id,
                             expected_revision=preview["source_revision"], confirmed_operation_id=preview["operation_id"])
    with pytest.raises(HomeKitWriteDisabled, match="Schreibfreigabe"):
        await standard.apply(preview["operation_id"], entry_id=entry.entry_id,
                             expected_revision=preview["source_revision"], confirmed_operation_id=preview["operation_id"], admin=True)
    assert entry.options["filter"]["include_entities"] == ["light.before"]

    service = HomeKitOperationService(hass, isolated_write_authority=True)
    plan = await service.plan_filter(entry_id=entry.entry_id, bridge=bridge, document=desired(entry.entry_id), inventory=inventory())
    args = {"entry_id": entry.entry_id, "expected_revision": plan["source_revision"], "confirmed_operation_id": plan["operation_id"]}
    with pytest.raises(HomeKitWriteBlocked):
        await service.apply(plan["operation_id"], **args)
    with pytest.raises(HomeKitWriteBlocked):
        await service.apply(plan["operation_id"], **(args | {"confirmed_operation_id": "wrong"}), admin=True)
    assert (await service.apply(plan["operation_id"], **args, admin=True))["state"] == "verification_incomplete"
    assert (await service.status(plan["operation_id"]))["state"] == "verification_incomplete"
    assert (await service.reconcile(plan["operation_id"]))["state"] == "verified"
    reopened = HomeKitOperationService(hass)
    assert (await reopened.reconcile(plan["operation_id"]))["state"] == "verified"
    with pytest.raises(HomeKitWriteBlocked, match="bereits begonnen"):
        await service.apply(plan["operation_id"], **args, admin=True)

    # A new process-like service cannot automatically retry an interrupted
    # request; it can only inspect the persisted preimage and current entry.
    second = await service.plan_filter(entry_id=entry.entry_id, bridge=bridge,
                                       document={"schema_version": 1, "bridges": {entry.entry_id: {"policy": "explicit_overrides", "entities": {"light.before": "exclude"}}}},
                                       inventory=[{"entity_id": "light.before", "homekit": {"configured_by_filter": True}, "compatibility": {"status": "supported"}}])
    await service._set_state(service._plans[second["operation_id"]], "applying")
    restarted = HomeKitOperationService(hass)
    assert (await restarted.status(second["operation_id"]))["state"] == "unknown_outcome"
    assert (await restarted.status(second["operation_id"]))["automatic_retry"] is False


async def test_yaml_operation_is_verified_by_core_only_in_isolation(hass, tmp_path, monkeypatch):
    async def no_network_start(_self):
        return None
    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    (tmp_path / "configuration.yaml").write_text("homekit: !include bridges.yaml\n")
    (tmp_path / "bridges.yaml").write_text(
        "- name: Operation YAML\n  port: 21083\n  filter:\n    include_entities:\n    - light.before\n"
    )
    assert await async_setup_component(hass, "homekit", await async_hass_config_yaml(hass))
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries("homekit")[0]
    service = HomeKitOperationService(hass, isolated_write_authority=True)
    bridge = {"entry_id": entry.entry_id, "source": "import", "filter": dict(entry.options["filter"])}
    plan = await service.plan_filter(entry_id=entry.entry_id, bridge=bridge, document=desired(entry.entry_id), inventory=inventory())
    result = await service.apply(plan["operation_id"], entry_id=entry.entry_id,
                                 expected_revision=plan["source_revision"], confirmed_operation_id=plan["operation_id"], admin=True)
    assert result["state"] == "verified"
    assert (await service.reconcile(plan["operation_id"]))["state"] == "verified"
    reopened = HomeKitOperationService(hass)
    assert (await reopened.reconcile(plan["operation_id"]))["state"] == "verified"
    assert "target_filter" not in (await reopened.status(plan["operation_id"]))
    assert "light.after" in hass.config_entries.async_get_entry(entry.entry_id).options["filter"]["include_entities"]
    neighbor = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="Native Neighbor",
        data={"name": "Native Neighbor", "port": 21084},
        options={"mode": "bridge", "filter": {}}, source=config_entries.SOURCE_USER,
        entry_id="native-neighbor-operation", unique_id=None, discovery_keys={}, subentries_data=None,
    )
    await hass.config_entries.async_add(neighbor)
    await hass.async_block_till_done()
    yaml_bytes = (tmp_path / "bridges.yaml").read_bytes()
    with pytest.raises(HomeKitWriteBlocked, match="native HomeKit-Entries"):
        await service.plan_filter(entry_id=entry.entry_id, bridge=bridge,
                                  document=desired(entry.entry_id), inventory=inventory())
    assert (tmp_path / "bridges.yaml").read_bytes() == yaml_bytes


async def test_reconcile_waits_for_running_native_apply(hass, monkeypatch):
    async def no_network_start(_self):
        return None
    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    entry = config_entries.ConfigEntry(
        version=1, minor_version=1, domain="homekit", title="Concurrent Operation",
        data={"name": "Concurrent Operation", "port": 21086},
        options={"mode": "bridge", "filter": {"include_entities": ["light.before"]}},
        source=config_entries.SOURCE_USER, entry_id="concurrent-native", unique_id=None,
        discovery_keys={}, subentries_data=None,
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    service = HomeKitOperationService(hass, isolated_write_authority=True)
    bridge = {"entry_id": entry.entry_id, "source": "user", "filter": dict(entry.options["filter"])}
    plan = await service.plan_filter(entry_id=entry.entry_id, bridge=bridge,
                                    document=desired(entry.entry_id), inventory=inventory())
    entered = asyncio.Event()
    release = asyncio.Event()
    original_apply = NativeHomeKitAdapter.apply

    async def delayed_apply(self, payload):
        entered.set()
        await release.wait()
        return await original_apply(self, payload)

    monkeypatch.setattr(NativeHomeKitAdapter, "apply", delayed_apply)
    applying = asyncio.create_task(service.apply(
        plan["operation_id"], entry_id=entry.entry_id,
        expected_revision=plan["source_revision"],
        confirmed_operation_id=plan["operation_id"], admin=True))
    await asyncio.wait_for(entered.wait(), timeout=5)
    reconciling = asyncio.create_task(service.reconcile(plan["operation_id"]))
    await asyncio.sleep(0)
    assert not reconciling.done()
    release.set()
    assert (await applying)["state"] == "verification_incomplete"
    assert (await reconciling)["state"] == "verified"
