"""Official-Core two-bridge HAP Apply acceptance worker for 0.10.31.

The worker deliberately uses the regular HomeKit Manager operation service,
including its persisted grant/revision checks. HAP verification is performed
by independent aiohomekit controllers after the Core-owned HomeKit reload and
again in a fresh Core process.
"""
from __future__ import annotations

import asyncio
import gc
import json
import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import aiohttp
from aiohomekit.controller.controller import Controller
from aiohomekit.controller.ip.discovery import IpDiscovery
from aiohomekit.controller.ip.pairing import IpPairing
from aiohomekit.exceptions import AuthenticationError
from aiohomekit.zeroconf import HomeKitService
from homeassistant import config_entries
from homeassistant.bootstrap import async_setup_hass
from homeassistant.components.homekit import HomeKit
from homeassistant.runner import RuntimeConfig
from port_allocator import reserve_hap_port, reserve_http_port

ENTRY_A = "acceptance-bridge-a-028"
ENTRY_B = "acceptance-bridge-b-028"
MANAGER_ENTRY = "acceptance-manager-028"
DOMAIN = "homekit_manager"
A_IDS = tuple(f"input_boolean.hkm_a_{index:02d}" for index in range(25))
B_IDS = tuple(f"input_boolean.hkm_b_{index:02d}" for index in range(25))
ALL_IDS = A_IDS + B_IDS


class LocalAdvertiser:
    """Keep the real HAP TCP driver but avoid LAN mDNS side effects."""

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


def _config_text(http_port: int) -> str:
    lines = [
        "homeassistant:",
        "  name: HKM 0.10.31 Acceptance",
        "http:",
        "  server_host: 127.0.0.1",
        f"  server_port: {http_port}",
        "logger:",
        "  default: critical",
        "input_boolean:",
    ]
    for entity_id in ALL_IDS:
        object_id = entity_id.split(".", 1)[1]
        lines.extend([f"  {object_id}:", f"    name: {object_id.replace('_', ' ').title()}"])
    return "\n".join(lines) + "\n"


def _filter(ids: tuple[str, ...]) -> dict[str, list[str]]:
    return {"include_entities": list(ids)}


def _entry(entry_id: str, title: str, port: int, ids: tuple[str, ...]):
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain="homekit",
        title=title,
        data={
            "name": title,
            "port": port,
            "ip_address": "127.0.0.1",
            "advertise_ip": ["127.0.0.1"],
        },
        options={"mode": "bridge", "filter": _filter(ids)},
        source=config_entries.SOURCE_USER,
        entry_id=entry_id,
        unique_id=None,
        discovery_keys={},
        subentries_data=None,
    )


def _write_grant(config_dir: Path, entry_id: str) -> None:
    now = datetime.now(UTC)
    payload = {
        "version": 1,
        "grant_id": "02802802802802802802802802802802",
        "entry_id": entry_id,
        "source": "user",
        "core_version": "2026.10.4",
        "allowed_fields": ["filter"],
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
    }
    path = config_dir / ".homekit_manager_write_grant.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)


def _install_isolated_custom_component(config_dir: Path) -> None:
    """Install the repository integration into this temporary HA instance."""
    source = Path(
        os.environ.get(
            "HKM_ACCEPTANCE_COMPONENT_SOURCE",
            str(Path(__file__).parents[2] / "custom_components" / DOMAIN),
        )
    )
    target = config_dir / "custom_components" / DOMAIN
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)


async def _wait_listener(port: int) -> None:
    for attempt in range(80):
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", port), 0.25
            )
        except (OSError, TimeoutError):
            if attempt == 79:
                raise AssertionError(f"HAP listener did not start on {port}") from None
            await asyncio.sleep(0.05)
        else:
            reader.feed_eof()
            writer.close()
            await writer.wait_closed()
            return


async def _pair(hass, homekit, pairing_id: str):
    await _wait_listener(homekit.driver.state.port)
    for attempt in range(1, 4):
        controller = Controller()
        discovery = IpDiscovery(
            controller, HomeKitService.from_service_info(homekit.driver.mdns_service_info)
        )
        try:
            print(f"acceptance: pairing {pairing_id} attempt={attempt}", flush=True)
            finish = await asyncio.wait_for(discovery.async_start_pairing(pairing_id), 15)
            pairing = await asyncio.wait_for(finish(homekit.driver.state.pincode.decode()), 15)
            await hass.async_add_executor_job(homekit.driver.persist)
            return pairing
        except AuthenticationError:
            if attempt == 3:
                raise
            await _wait_listener(homekit.driver.state.port)
        finally:
            await discovery.close()
    raise AssertionError("pairing loop exhausted")


async def _accessories(pairing):
    return await asyncio.wait_for(pairing.list_accessories_and_characteristics(), 15)


async def _ws_call(hass, http_port: int, message: dict) -> dict:
    """Execute one authenticated operation through the real HA WebSocket."""
    users = await hass.auth.async_get_users()
    admin = next((user for user in users if user.is_admin), None)
    if admin is None:
        admin = await hass.auth.async_create_user(
            "HKM Acceptance Administrator", group_ids=["system-admin"]
        )
    refresh = await hass.auth.async_create_refresh_token(
        admin, client_id=f"http://127.0.0.1:{http_port}"
    )
    access_token = hass.auth.async_create_access_token(refresh)
    async with (
        aiohttp.ClientSession() as session,
        session.ws_connect(f"ws://127.0.0.1:{http_port}/api/websocket") as ws,
    ):
            hello = await asyncio.wait_for(ws.receive_json(), 10)
            assert hello["type"] == "auth_required", hello
            await ws.send_json({"type": "auth", "access_token": access_token})
            auth = await asyncio.wait_for(ws.receive_json(), 10)
            assert auth["type"] == "auth_ok", auth
            request = dict(message)
            request["id"] = 1
            await ws.send_json(request)
            response = await asyncio.wait_for(ws.receive_json(), 30)
            assert response["id"] == 1, response
            assert response["type"] == "result", response
            assert response["success"], response
            return response["result"]


def _names(accessories) -> set[str]:
    values: set[str] = set()
    for accessory in accessories:
        for service in accessory.get("services", []):
            for characteristic in service.get("characteristics", []):
                if characteristic.get("type") == "00000023-0000-1000-8000-0026BB765291":
                    value = characteristic.get("value")
                    if isinstance(value, str):
                        values.add(value)
    return values


def _shape(accessories) -> list[dict]:
    return [
        {
            "aid": accessory.get("aid"),
            "iids": sorted(
                iid
                for service in accessory.get("services", [])
                for iid in [
                    service.get("iid"),
                    *(item.get("iid") for item in service.get("characteristics", [])),
                ]
                if iid is not None
            ),
        }
        for accessory in accessories
    ]


def _signature_by_name(accessories) -> dict[str, dict]:
    result = {}
    for accessory in accessories:
        name = next(
            (
                characteristic.get("value")
                for service in accessory.get("services", [])
                for characteristic in service.get("characteristics", [])
                if characteristic.get("type") == "00000023-0000-1000-8000-0026BB765291"
                and isinstance(characteristic.get("value"), str)
            ),
            None,
        )
        if name is not None:
            result[name] = {
                "aid": accessory.get("aid"),
                "iids": sorted(
                    iid
                    for service in accessory.get("services", [])
                    for iid in [
                        service.get("iid"),
                        *(item.get("iid") for item in service.get("characteristics", [])),
                    ]
                    if iid is not None
                ),
            }
    return result


async def run() -> None:
    shared = Path(os.environ["HKM_ACCEPTANCE_DIR"])
    phase = os.environ["HKM_ACCEPTANCE_PHASE"]
    print(f"acceptance: phase={phase} dir={shared}", flush=True)
    shared.mkdir(parents=True, exist_ok=True)
    config_dir = shared / "config"
    config_dir.mkdir(exist_ok=True)

    with patch(
        "homeassistant.components.homekit.zeroconf.async_get_async_instance",
        local_advertiser,
    ), patch.object(HomeKit, "_async_show_setup_message", lambda _self: None):
        if phase == "pair_apply":
            http_port = reserve_http_port(str(config_dir))
            _install_isolated_custom_component(config_dir)
            (config_dir / "configuration.yaml").write_text(
                _config_text(http_port), encoding="utf-8"
            )
            print(f"acceptance: configuration written port={http_port}", flush=True)
        elif phase == "reconnect":
            _install_isolated_custom_component(config_dir)
        print("acceptance: starting async_setup_hass", flush=True)
        hass = await async_setup_hass(
            RuntimeConfig(config_dir=str(config_dir), skip_pip=True,
                          log_file=str(shared / "home-assistant.log"))
        )
        print("acceptance: async_setup_hass returned", flush=True)
        assert hass is not None
        await hass.async_block_till_done()
        print("acceptance: initial setup complete", flush=True)

        for entity_id in ALL_IDS:
            if hass.states.get(entity_id) is None:
                hass.states.async_set(entity_id, "off", {"friendly_name": entity_id})
        await hass.async_block_till_done()

        if phase == "pair_apply":
            port_a = reserve_hap_port(str(shared / "bridge-a"))
            port_b = reserve_hap_port(str(shared / "bridge-b"))
            entry_a = _entry(ENTRY_A, "HKM Acceptance A", port_a, A_IDS)
            entry_b = _entry(ENTRY_B, "HKM Acceptance B", port_b, B_IDS)
            manager = config_entries.ConfigEntry(
                version=1, minor_version=1, domain=DOMAIN, title="HomeKit Manager",
                data={}, options={}, source=config_entries.SOURCE_USER,
                entry_id=MANAGER_ENTRY, unique_id=None, discovery_keys={},
                subentries_data=None,
            )
            await hass.config_entries.async_add(entry_a)
            await hass.config_entries.async_add(entry_b)
            await hass.config_entries.async_add(manager)
            await hass.config_entries._store.async_save(hass.config_entries._data_to_save())
            _write_grant(config_dir, ENTRY_A)
        else:
            entry_a = hass.config_entries.async_get_entry(ENTRY_A)
            entry_b = hass.config_entries.async_get_entry(ENTRY_B)
            assert entry_a is not None and entry_b is not None
            port_a = entry_a.data["port"]
            port_b = entry_b.data["port"]

        await hass.async_start()
        await hass.async_block_till_done()
        print(
            "acceptance: post-start entries "
            + repr(
                [
                    (item.entry_id, item.domain, item.state.value, item.reason)
                    for item in hass.config_entries.async_entries()
                ]
            ),
            flush=True,
        )
        for entry_id in (ENTRY_A, ENTRY_B, MANAGER_ENTRY):
            entry = hass.config_entries.async_get_entry(entry_id)
            assert entry is not None
            if entry.state.value != "loaded":
                setup_ok = await hass.config_entries.async_setup(entry_id)
                print(
                    f"acceptance: setup entry={entry_id} ok={setup_ok} "
                    f"state={entry.state} reason={entry.reason}",
                    flush=True,
                )
                assert setup_ok
                await hass.async_block_till_done()
            assert entry.state.value == "loaded", (entry_id, entry.state)

        homekit_a = hass.config_entries.async_get_entry(ENTRY_A).runtime_data.homekit
        homekit_b = hass.config_entries.async_get_entry(ENTRY_B).runtime_data.homekit
        assert homekit_a.status == 1 and homekit_b.status == 1

        if phase == "pair_apply":
            pairing_a = await _pair(hass, homekit_a, "hkm-acceptance-a-028")
            pairing_b = await _pair(hass, homekit_b, "hkm-acceptance-b-028")
            before_a = await _accessories(pairing_a)
            before_b = await _accessories(pairing_b)
            (shared / "pairing-a.json").write_text(json.dumps(pairing_a.pairing_data), encoding="utf-8")
            (shared / "pairing-b.json").write_text(json.dumps(pairing_b.pairing_data), encoding="utf-8")
            (shared / "pairing-a.json").chmod(0o600)
            (shared / "pairing-b.json").chmod(0o600)
            baseline = {
                "manager_version": json.loads(
                    (config_dir / "custom_components" / DOMAIN / "manifest.json").read_text()
                )["version"],
                "a": {"entry_id": ENTRY_A, "mac": homekit_a.driver.state.mac, "port": port_a,
                      "shape": _shape(before_a), "signatures": _signature_by_name(before_a),
                      "names": sorted(_names(before_a))},
                "b": {"entry_id": ENTRY_B, "mac": homekit_b.driver.state.mac, "port": port_b,
                      "shape": _shape(before_b), "signatures": _signature_by_name(before_b),
                      "names": sorted(_names(before_b))},
            }
            (shared / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")

            coordinator = hass.data[DOMAIN]["coordinator"]
            await coordinator.async_refresh(ENTRY_A)
            assert coordinator.selected_bridge_id == ENTRY_A
            desired = {entity_id: "include" for entity_id in A_IDS[1:]}
            desired[B_IDS[0]] = "include"
            desired[A_IDS[0]] = "exclude"
            document = {"schema_version": 1, "bridges": {ENTRY_A: {"policy": "explicit_overrides", "entities": desired}}}
            upgrade_baseline = os.environ.get("HKM_ACCEPTANCE_SKIP_APPLY") == "1"
            if upgrade_baseline:
                result = {"state": "upgrade_baseline", "runtime_verification": "not_run"}
            else:
                plan = await _ws_call(
                    hass,
                    http_port,
                    {
                        "type": "homekit_manager/operation_plan",
                        "document": document,
                        "entry_id": ENTRY_A,
                        "expected_fingerprint": coordinator.fingerprint,
                    },
                )
                assert plan["apply_enabled"] is True, plan
                result = await _ws_call(
                    hass,
                    http_port,
                    {
                        "type": "homekit_manager/operation_apply",
                        "operation_id": plan["operation_id"],
                        "entry_id": ENTRY_A,
                        "source_revision": plan["source_revision"],
                        "expected_fingerprint": coordinator.fingerprint,
                        "confirmed_operation_id": plan["operation_id"],
                    },
                )
                assert result["state"] == "verified"
                assert result["runtime_verification"] == "verified"
            await hass.async_block_till_done()

            controller_a = Controller()
            controller_b = Controller()
            reconnect_a = IpPairing(controller_a, pairing_a.pairing_data)
            reconnect_b = IpPairing(controller_b, pairing_b.pairing_data)
            after_a = await _accessories(reconnect_a)
            after_b = await _accessories(reconnect_b)
            assert homekit_a.driver.state.mac == baseline["a"]["mac"]
            assert homekit_b.driver.state.mac == baseline["b"]["mac"]
            if upgrade_baseline:
                assert _names(after_a) == _names(before_a)
            else:
                assert _names(after_a) != _names(before_a)
            assert _names(after_b) == _names(before_b)
            if not upgrade_baseline:
                assert _names(after_a) == {_name for _name in _names(before_a) if "Hkm A 00" not in _name} | {"Hkm B 00"}
            assert _shape(after_b) == baseline["b"]["shape"]
            before_signatures_a = baseline["a"]["signatures"]
            after_signatures_a = _signature_by_name(after_a)
            for name in before_signatures_a:
                if upgrade_baseline or name != "Hkm A 00":
                    assert after_signatures_a[name] == before_signatures_a[name]
            # The independent controllers reached both live bridges with the
            # persisted pairing data; retain this as explicit evidence instead
            # of relying on the accessory comparison alone.
            result["pairing_verified"] = True
            assert len([entry for entry in hass.config_entries.async_entries("homekit")]) == 2
            (shared / "after_apply.json").write_text(json.dumps({
                "a": {"entry_id": ENTRY_A, "mac": homekit_a.driver.state.mac, "port": port_a,
                      "shape": _shape(after_a), "signatures": after_signatures_a,
                      "names": sorted(_names(after_a))},
                "b": {"entry_id": ENTRY_B, "mac": homekit_b.driver.state.mac, "port": port_b,
                      "shape": _shape(after_b), "signatures": _signature_by_name(after_b),
                      "names": sorted(_names(after_b))},
                "result": result,
            }), encoding="utf-8")
            await reconnect_a.shutdown()
            await reconnect_b.shutdown()
            await pairing_a.shutdown()
            await pairing_b.shutdown()
        elif phase == "reconnect":
            baseline = json.loads((shared / "baseline.json").read_text(encoding="utf-8"))
            expected = json.loads((shared / "after_apply.json").read_text(encoding="utf-8"))
            current_version = json.loads(
                (config_dir / "custom_components" / DOMAIN / "manifest.json").read_text()
            )["version"]
            assert current_version == "0.10.31"
            pairing_a = IpPairing(Controller(), json.loads((shared / "pairing-a.json").read_text(encoding="utf-8")))
            pairing_b = IpPairing(Controller(), json.loads((shared / "pairing-b.json").read_text(encoding="utf-8")))
            after_a = await _accessories(pairing_a)
            after_b = await _accessories(pairing_b)
            assert homekit_a.driver.state.mac == baseline["a"]["mac"]
            assert homekit_b.driver.state.mac == baseline["b"]["mac"]
            assert sorted(_names(after_a)) == expected["a"]["names"]
            assert sorted(_names(after_b)) == baseline["b"]["names"]
            assert _shape(after_b) == baseline["b"]["shape"]
            assert _signature_by_name(after_b) == baseline["b"]["signatures"]
            assert len([entry for entry in hass.config_entries.async_entries("homekit")]) == 2
            await pairing_a.shutdown()
            await pairing_b.shutdown()
        else:
            raise ValueError(f"Unknown phase: {phase}")

        await hass.async_stop(force=True)
    gc.freeze()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except BaseException:
        import traceback

        traceback.print_exc()
        raise
