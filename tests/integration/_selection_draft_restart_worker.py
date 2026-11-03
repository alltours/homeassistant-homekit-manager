"""Run one isolated Home Assistant process for the 0.10.32/0.10.33 upgrade test."""
from __future__ import annotations

import asyncio
import gc
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import aiohttp
from homeassistant import config_entries
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.bootstrap import async_setup_hass
from homeassistant.components.homekit import HomeKit
from homeassistant.runner import RuntimeConfig
from port_allocator import reserve_hap_port, reserve_http_port

ENTRY_ID = "isolated-upgrade-bridge"
ENTITY_ID = "light.upgrade_fixture"


class LocalAdvertiser:
    """Keep the isolated HAP setup off the LAN while exercising real Core."""

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


async def _websocket_call(url: str, token: str, message: dict) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(f"{url}/api/websocket") as websocket:
            assert (await websocket.receive_json())["type"] == "auth_required"
            await websocket.send_json({"type": "auth", "access_token": token})
            assert (await websocket.receive_json())["type"] == "auth_ok"
            await websocket.send_json({"id": 1, **message})
            response = await websocket.receive_json()
            assert response["id"] == 1
            return response


async def _admin_token(hass):
    user = await hass.auth.async_create_user(
        "isolated-upgrade-admin", group_ids=[GROUP_ID_ADMIN]
    )
    refresh = await hass.auth.async_create_refresh_token(user, "isolated-upgrade")
    return hass.auth.async_create_access_token(refresh)


async def run() -> None:
    phase = os.environ["HKM_UPGRADE_PHASE"]
    config_dir = Path(os.environ["HKM_UPGRADE_CONFIG_DIR"])
    config_dir.mkdir(parents=True, exist_ok=True)
    http_port = int(os.environ.get("HKM_UPGRADE_HTTP_PORT", "0"))
    if phase == "legacy":
        if not http_port:
            http_port = reserve_http_port(str(config_dir))
        hap_port = reserve_hap_port(str(config_dir))
        (config_dir / "configuration.yaml").write_text(
            "homeassistant:\n  name: Isolated Upgrade\n"
            f"http:\n  server_port: {http_port}\n"
            "logger:\n  default: critical\n",
            encoding="utf-8",
        )
    else:
        checkpoint = json.loads((config_dir / "upgrade_checkpoint.json").read_text())
        http_port = checkpoint["http_port"]

    with patch(
        "homeassistant.components.homekit.zeroconf.async_get_async_instance",
        _local_advertiser,
    ), patch.object(HomeKit, "_async_show_setup_message", lambda _self: None):
        hass = await async_setup_hass(RuntimeConfig(
            config_dir=str(config_dir),
            skip_pip=True,
            log_file=str(config_dir / f"home-assistant-{phase}.log"),
        ))
        assert hass is not None
        hass.states.async_set(ENTITY_ID, "on", {"friendly_name": "Upgrade fixture"})
        await hass.async_block_till_done()

        if phase == "legacy":
            entry = config_entries.ConfigEntry(
                version=1,
                minor_version=1,
                domain="homekit",
                title="Isolated Upgrade Bridge",
                data={
                    "name": "Isolated Upgrade Bridge",
                    "mode": "bridge",
                    "port": hap_port,
                    "ip_address": "127.0.0.1",
                    "advertise_ip": ["127.0.0.1"],
                },
                options={
                    "mode": "bridge",
                    "filter": {"include_entities": [ENTITY_ID]},
                },
                source=config_entries.SOURCE_USER,
                entry_id=ENTRY_ID,
                unique_id=None,
                discovery_keys={},
                subentries_data=None,
            )
            await hass.config_entries.async_add(entry)
            await hass.config_entries._store.async_save(hass.config_entries._data_to_save())
        else:
            entry = hass.config_entries.async_get_entry(ENTRY_ID)
            assert entry is not None
            assert entry.data["port"] == checkpoint["hap_port"]
            assert entry.options == checkpoint["native_options"]

        await hass.async_start()
        await hass.async_block_till_done()
        if entry.state.value != "loaded":
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
        assert entry.state.value == "loaded"

        integration = __import__(
            "custom_components.homekit_manager", fromlist=["async_setup"]
        )
        assert await integration.async_setup(hass, {})
        await hass.async_block_till_done()
        coordinator = hass.data["homekit_manager"]["coordinator"]
        assert coordinator.selected_bridge() is not None
        assert coordinator.operation_policy["enabled"] is False

        if phase == "legacy":
            from custom_components.homekit_manager.yaml_store import YamlStore

            legacy_document = {
                "schema_version": 1,
                "bridges": {
                    ENTRY_ID: {
                        "policy": "explicit_overrides",
                        "entities": {ENTITY_ID: "exclude"},
                    }
                },
            }
            store = YamlStore(config_dir / "homekit_manager.yaml")
            await hass.async_add_executor_job(store.save, legacy_document, None)
            await hass.async_add_executor_job(
                lambda: (config_dir / "upgrade_checkpoint.json").write_text(
                    json.dumps({
                        "http_port": http_port,
                        "hap_port": hap_port,
                        "entry_id": entry.entry_id,
                        "native_options": deepcopy(dict(entry.options)),
                        "legacy_document": legacy_document,
                    }, sort_keys=True),
                    encoding="utf-8",
                )
            )
        elif phase == "save":
            token = await _admin_token(hass)
            url = f"http://127.0.0.1:{http_port}"
            draft_response = await _websocket_call(
                url, token, {"type": "homekit_manager/selection_draft"}
            )
            assert draft_response["success"] is True, draft_response
            model = draft_response["result"]
            draft = deepcopy(model["draft"])
            if model["entities"]:
                entity = model["entities"][0]
                draft["decisions"][entity["entity_id"]] = {
                    "decision": "KEEP", "identity": entity["identity"]
                }
            save_response = await _websocket_call(
                url,
                token,
                {
                    "type": "homekit_manager/save_selection_draft",
                    "draft": draft,
                    "expected_revision": model["snapshot"]["snapshot_revision"],
                    "expected_fingerprint": model["snapshot"]["snapshot_fingerprint"],
                },
            )
            assert save_response["success"] is True, save_response
            saved = save_response["result"]["draft"]
            assert saved["bridge_entry_id"] == ENTRY_ID
            assert dict(entry.options) == checkpoint["native_options"]
            assert coordinator.operation_policy["enabled"] is False
            (config_dir / "saved_draft.json").write_text(
                json.dumps(saved, sort_keys=True), encoding="utf-8"
            )
            assert (config_dir / ".storage" / "homekit_manager.selection_drafts").is_file()
        else:
            token = await _admin_token(hass)
            response = await _websocket_call(
                f"http://127.0.0.1:{http_port}",
                token,
                {"type": "homekit_manager/selection_draft"},
            )
            assert response["success"] is True, response
            loaded = response["result"]["draft"]
            saved = json.loads((config_dir / "saved_draft.json").read_text())
            for field in ("bridge_entry_id", "decisions", "tombstones", "stale_includes"):
                assert loaded[field] == saved[field], field
            assert loaded["bridge_entry_id"] == checkpoint["entry_id"]
            assert dict(entry.options) == checkpoint["native_options"]
            assert coordinator.operation_policy["enabled"] is False
            (config_dir / "restart_verified.json").write_text(
                json.dumps({
                    "entry_id": entry.entry_id,
                    "native_options_unchanged": dict(entry.options) == checkpoint["native_options"],
                    "draft_reloaded": True,
                    "write_enabled": coordinator.operation_policy["enabled"],
                }, sort_keys=True),
                encoding="utf-8",
            )
        await hass.async_stop(force=True)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except BaseException as err:
        print(f"upgrade-worker failed: {err!r}", file=sys.stderr, flush=True)
        raise
    # Python 3.14/macOS can crash while collecting objects from a stopped HA
    # loop.  The process has completed all assertions before this point; keep
    # final collection from turning a successful isolated process into a
    # spurious failure.
    gc.freeze()
