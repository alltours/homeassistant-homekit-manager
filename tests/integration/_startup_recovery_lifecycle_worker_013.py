"""Full Home Assistant startup boundary test for native recovery observation."""
from __future__ import annotations

import asyncio
import gc
import json
import os
import socket
from pathlib import Path
from unittest.mock import patch

from homeassistant.bootstrap import async_setup_hass
from homeassistant.components import homekit as homekit_component
from homeassistant.components.homekit import HomeKit
from homeassistant.runner import RuntimeConfig

from custom_components.homekit_manager import async_setup as manager_async_setup
from custom_components.homekit_manager.const import DOMAIN
from custom_components.homekit_manager.migration_journal import (
    JournalRecord,
    JournalStore,
)


class LocalAdvertiser:
    """Suppress mDNS publication while retaining the real HAP listener."""

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


async def local_addresses(_hass):
    return ["127.0.0.1"]


def free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]


def _append_marker(path: Path, marker: str) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(marker + "\n")


async def run() -> None:
    shared = Path(os.environ["HKM_STARTUP_RECOVERY_DIR"])
    repo_root = Path(os.environ["HKM_REPO_ROOT"])
    shared.mkdir(mode=0o700, parents=True, exist_ok=True)
    (shared / ".storage").mkdir(mode=0o700, exist_ok=True)
    custom_components = shared / "custom_components"
    custom_components.mkdir(mode=0o700, exist_ok=True)
    (custom_components / "homekit_manager").symlink_to(
        repo_root / "custom_components" / "homekit_manager",
        target_is_directory=True,
    )

    port = free_loopback_port()
    (shared / "configuration.yaml").write_text(
        "homeassistant:\n"
        "  name: Isolated Startup Recovery\n"
        "input_boolean:\n"
        "  startup_recovery_test:\n"
        "    name: Startup Recovery Test\n"
        "homekit_manager: {}\n"
        "homekit:\n"
        f"  - name: Startup Recovery HK\n"
        f"    port: {port}\n"
        "    ip_address: 127.0.0.1\n"
        "    advertise_ip:\n"
        "      - 127.0.0.1\n"
        "    filter:\n"
        "      include_entities:\n"
        "        - input_boolean.startup_recovery_test\n"
        "logger:\n"
        "  default: critical\n",
        encoding="utf-8",
    )
    journal_path = shared / ".storage" / "homekit_manager.native_migration.journal.json"
    journal = JournalRecord.new(
        bridge_id="unresolved-entry",
        source="import",
        target="user",
        baseline_fingerprint="baseline",
        config_revision="revision",
    ).advance(state="SOURCE_SWITCHING")
    JournalStore(journal_path).save(journal)
    journal_before = journal_path.read_bytes()
    markers = shared / "lifecycle.markers"

    async def marked_homekit_setup(hass, config):
        _append_marker(markers, "homekit.async_setup.start")
        result = await original_homekit_setup(hass, config)
        _append_marker(markers, "homekit.async_setup.end")
        return result

    async def marked_manager_setup(hass, config):
        _append_marker(markers, "homekit_manager.async_setup.start")
        result = await manager_async_setup(hass, config)
        _append_marker(markers, "homekit_manager.async_setup.end")
        return result

    original_homekit_setup = homekit_component.async_setup
    with (
        patch("homeassistant.components.homekit.zeroconf.async_get_async_instance", local_advertiser),
        patch("homeassistant.components.homekit.network.async_get_announce_addresses", local_addresses),
        patch.object(HomeKit, "_async_show_setup_message", lambda _self: None),
        patch.object(homekit_component, "async_setup", marked_homekit_setup),
        patch("custom_components.homekit_manager.async_setup", marked_manager_setup),
    ):
        hass = await async_setup_hass(
            RuntimeConfig(
                config_dir=str(shared),
                skip_pip=True,
                log_file=str(shared / "home-assistant.log"),
            )
        )
        assert hass is not None
        await hass.async_block_till_done()
        await hass.async_start()
        await hass.async_block_till_done()

        entries = hass.config_entries.async_entries("homekit")
        assert len(entries) == 1
        assert entries[0].source == "import"
        assert entries[0].runtime_data.homekit.driver is not None
        assert entries[0].runtime_data.homekit.status == 1
        startup = hass.data[DOMAIN]["startup_recovery"]
        assert startup["action"] == "manual_recovery"
        assert startup["automatic"] is False
        assert startup["native_mutation_allowed"] is False
        assert journal_path.read_bytes() == journal_before
        await hass.async_stop(force=True)

    observed_markers = markers.read_text(encoding="utf-8").splitlines()
    assert observed_markers.index("homekit.async_setup.end") < observed_markers.index(
        "homekit_manager.async_setup.start"
    )
    (shared / "observed.json").write_text(
        json.dumps(
            {
                "entry_count": len(entries),
                "entry_source": entries[0].source,
                "startup_recovery": startup,
                "markers": observed_markers,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(run())
    gc.freeze()
