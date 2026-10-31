"""Local, narrow and revocable authority for a HomeKit filter apply.

The grant is deliberately outside Home Assistant's WebSocket and draft stores.
An administrator with configuration-directory access must create it separately.
Every production apply re-reads the file immediately before the writer runs.
"""
from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .const import SUPPORTED_CORE_VERSION
from .safety import has_extended_acl

GRANT_FILENAME = ".homekit_manager_write_grant.json"
_KEYS = frozenset({"version", "grant_id", "entry_id", "source", "core_version", "allowed_fields", "issued_at", "expires_at"})


class GrantBlocked(ValueError):
    """The local authority is absent, invalid, expired or revoked."""


@dataclass(frozen=True)
class ProductionWriteGrant:
    grant_id: str
    entry_id: str
    source: str
    expires_at: datetime
    device: int
    inode: int
    modified_ns: int

    async def verify(self, hass: Any, entry_id: str, source: str) -> None:
        current = await read_production_grant(hass)
        if current != self or entry_id != self.entry_id or source != self.source:
            raise GrantBlocked("Lokale HomeKit-Schreibfreigabe wurde geändert oder widerrufen")

    def verify_sync(self, hass: Any, entry_id: str, source: str) -> None:
        """Recheck inside an executor job immediately before a file mutation."""
        current = _read(Path(hass.config.config_dir) / GRANT_FILENAME)
        if current != self or entry_id != self.entry_id or source != self.source:
            raise GrantBlocked("Lokale HomeKit-Schreibfreigabe wurde geändert oder widerrufen")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise GrantBlocked("Doppeltes Feld in der HomeKit-Schreibfreigabe")
        value[key] = item
    return value


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise GrantBlocked("Ungültiger Zeitstempel in der HomeKit-Schreibfreigabe")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))  # noqa: FURB162 - supports older Python runtimes
    except ValueError as err:
        raise GrantBlocked("Ungültiger Zeitstempel in der HomeKit-Schreibfreigabe") from err
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GrantBlocked("HomeKit-Schreibfreigabe benötigt UTC-Zeitstempel")
    return parsed.astimezone(UTC)


def _read(path: Path) -> ProductionWriteGrant | None:
    try:
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as err:
        raise GrantBlocked("Verzeichnis der HomeKit-Schreibfreigabe ist nicht sicher lesbar") from err
    try:
        directory = os.fstat(parent)
        if not stat.S_ISDIR(directory.st_mode) or directory.st_uid != os.geteuid() or directory.st_mode & 0o022 or has_extended_acl(parent):
            raise GrantBlocked("Verzeichnis der HomeKit-Schreibfreigabe muss dem HA-Prozess gehören und darf nicht gemeinsam beschreibbar sein")
        try:
            descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=parent)
        except FileNotFoundError:
            return None
        except OSError as err:
            raise GrantBlocked("HomeKit-Schreibfreigabe kann nicht sicher gelesen werden") from err
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600 or has_extended_acl(descriptor):
                raise GrantBlocked("HomeKit-Schreibfreigabe benötigt eine eigene reguläre Datei mit Modus 0600 ohne ACL")
            if info.st_size < 2 or info.st_size > 4096:
                raise GrantBlocked("HomeKit-Schreibfreigabe hat eine ungültige Dateigröße")
            raw = os.read(descriptor, 4097)
            after = os.fstat(descriptor)
            if len(raw) != info.st_size or (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size) != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size):
                raise GrantBlocked("HomeKit-Schreibfreigabe wurde beim Lesen verändert")
        finally:
            os.close(descriptor)
    except OSError as err:
        raise GrantBlocked("Dateiberechtigungen der HomeKit-Schreibfreigabe konnten nicht geprüft werden") from err
    finally:
        os.close(parent)
    try:
        data = json.loads(raw, object_pairs_hook=_unique_pairs)
    except (UnicodeError, json.JSONDecodeError) as err:
        raise GrantBlocked("HomeKit-Schreibfreigabe ist kein gültiges JSON") from err
    if not isinstance(data, dict) or set(data) != _KEYS:
        raise GrantBlocked("HomeKit-Schreibfreigabe enthält fehlende oder unbekannte Felder")
    if type(data["version"]) is not int or data["version"] != 1 or data["core_version"] != SUPPORTED_CORE_VERSION:
        raise GrantBlocked("Version der HomeKit-Schreibfreigabe oder Core-Version passt nicht")
    if not isinstance(data["grant_id"], str) or re.fullmatch(r"[0-9a-f]{32}", data["grant_id"]) is None:
        raise GrantBlocked("HomeKit-Schreibfreigabe benötigt eine zufällige 128-Bit-ID")
    if not isinstance(data["entry_id"], str) or not data["entry_id"] or len(data["entry_id"]) > 128:
        raise GrantBlocked("Ungültige Bridge-ID in der HomeKit-Schreibfreigabe")
    if not isinstance(data["source"], str) or data["source"] not in {"user", "import"} or data["allowed_fields"] != ["filter"]:
        raise GrantBlocked("HomeKit-Schreibfreigabe ist zu breit oder hat eine ungültige Quelle")
    issued, expires = _timestamp(data["issued_at"]), _timestamp(data["expires_at"])
    now = datetime.now(UTC)
    if issued > now or expires <= now or expires > issued + timedelta(hours=24):
        raise GrantBlocked("HomeKit-Schreibfreigabe ist noch nicht gültig, abgelaufen oder länger als 24 Stunden")
    return ProductionWriteGrant(data["grant_id"], data["entry_id"], data["source"], expires,
                                info.st_dev, info.st_ino, info.st_mtime_ns)


async def read_production_grant(hass: Any) -> ProductionWriteGrant | None:
    """Read only; absence means disabled and malformed files fail closed."""
    path = Path(hass.config.config_dir) / GRANT_FILENAME
    return await hass.async_add_executor_job(lambda: _read(path))
