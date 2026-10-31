"""Safe, versioned persistence for the HomeKit Manager desired state.

This module deliberately has no Home Assistant dependency.  It stores only
the desired entity overrides; HomeKit pairing data and ConfigEntry data never
enter this file.
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
import threading
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows development fallback
    fcntl = None

from .const import SCHEMA_VERSION

_ENTITY_ID = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
_POLICIES = frozenset({"explicit_overrides", "positive_list"})
_SENSITIVE = ("password", "token", "secret", "pin", "key", "pairing")
_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


class YamlStoreError(Exception):
    """Base class for desired-state storage errors."""


class YamlValidationError(YamlStoreError, ValueError):
    """The YAML document does not match the supported schema."""


class YamlVersionConflict(YamlStoreError):
    """The file changed after the caller read it."""


class YamlWriteError(YamlStoreError, OSError):
    """The atomic write could not be completed."""


@dataclass(frozen=True)
class YamlSnapshot:
    """A validated read of the desired-state file."""

    document: dict[str, Any]
    file_version: str | None
    exists: bool
    valid: bool
    error: str | None
    last_modified: str | None


def empty_document() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "bridges": {}}


def _lock_for(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _locks_guard:
        return _locks.setdefault(key, threading.RLock())


def _is_sensitive(key: str) -> bool:
    lowered = key.casefold()
    return any(word in lowered for word in _SENSITIVE)


def _validate_entity_id(value: Any, location: str) -> str:
    if not isinstance(value, str) or not _ENTITY_ID.fullmatch(value):
        raise YamlValidationError(f"{location} enthält keine gültige Entity-ID")
    return value


def validate_document(document: Any) -> dict[str, Any]:
    """Validate and canonically normalize a desired-state document."""
    if not isinstance(document, Mapping):
        raise YamlValidationError("Dokument muss ein Mapping sein")
    if set(document) - {"schema_version", "bridges"}:
        raise YamlValidationError("Unbekannte Top-Level-Schlüssel")
    if type(document.get("schema_version")) is not int or document.get("schema_version") != SCHEMA_VERSION:
        raise YamlValidationError(f"Unbekannte Schema-Version: {document.get('schema_version')!r}")
    bridges = document.get("bridges")
    if not isinstance(bridges, Mapping):
        raise YamlValidationError("bridges muss ein Mapping sein")

    normalized_bridges: dict[str, Any] = {}
    if any(not isinstance(key, str) for key in bridges):
        raise YamlValidationError("Bridge-IDs müssen Zeichenketten sein")
    for entry_id in sorted(bridges):
        if not isinstance(entry_id, str) or not entry_id or _is_sensitive(entry_id):
            raise YamlValidationError("Ungültige Bridge-ID")
        bridge = bridges[entry_id]
        if not isinstance(bridge, Mapping):
            raise YamlValidationError(f"bridges.{entry_id} muss ein Mapping sein")
        if set(bridge) - {"policy", "entities", "migration_acknowledged"}:
            raise YamlValidationError(f"Unbekannte Schlüssel in bridges.{entry_id}")
        if bridge.get("policy") not in _POLICIES:
            raise YamlValidationError(f"bridges.{entry_id}.policy muss eine unterstützte Filterstrategie sein")
        acknowledged = bridge.get("migration_acknowledged", False)
        if type(acknowledged) is not bool or (acknowledged and bridge["policy"] != "positive_list"):
            raise YamlValidationError("Migrationsbestätigung gilt nur für eine Positivliste")
        entities = bridge.get("entities")
        if not isinstance(entities, Mapping):
            raise YamlValidationError(f"bridges.{entry_id}.entities muss ein Mapping sein")
        normalized_entities: dict[str, str] = {}
        if any(not isinstance(key, str) for key in entities):
            raise YamlValidationError("Entity-IDs müssen Zeichenketten sein")
        for entity_id in sorted(entities):
            entity_id = _validate_entity_id(entity_id, f"bridges.{entry_id}.entities")
            status = entities[entity_id]
            if not isinstance(status, str) or status not in {"include", "exclude"}:
                raise YamlValidationError(f"Ungültiger Status für {entity_id}: {status!r}")
            normalized_entities[entity_id] = status
        normalized_bridges[entry_id] = {"policy": bridge["policy"], "entities": normalized_entities}
        if acknowledged:
            normalized_bridges[entry_id]["migration_acknowledged"] = True
    return {"schema_version": SCHEMA_VERSION, "bridges": normalized_bridges}


def _dump(document: Mapping[str, Any]) -> bytes:
    normalized = validate_document(document)
    return yaml.safe_dump(
        normalized, allow_unicode=True, default_flow_style=False,
        sort_keys=False, explicit_start=False,
    ).encode("utf-8")


def document_version(document: Mapping[str, Any]) -> str:
    """Return the stable version of normalized document content."""
    return hashlib.sha256(_dump(document)).hexdigest()


class YamlStore:
    """Thread-safe optimistic-concurrency store using same-directory replace."""

    def __init__(self, path: str | os.PathLike[str] = "/config/homekit_manager.yaml"):
        self.path = Path(path)
        self._lock = _lock_for(self.path)

    @property
    def backup_path(self) -> Path:
        """Return the side-by-side backup path used before replacement."""
        return self.path.with_name(f"{self.path.name}.bak")

    @property
    def lock_path(self) -> Path:
        """Return the cross-process lock path for this store."""
        return self.path.with_name(f".{self.path.name}.lock")

    @contextmanager
    def _file_lock(self):
        """Serialize writers across threads and independent processes."""
        if fcntl is None:
            yield
            return
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _backup_current(self, content: bytes) -> None:
        """Atomically preserve the current file before replacing it."""
        if not self.path.exists():
            return
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "wb", dir=self.path.parent, prefix=f".{self.backup_path.name}.", suffix=".tmp", delete=False
            ) as backup_file:
                temporary = backup_file.name
                backup_file.write(content)
                backup_file.flush()
                os.fsync(backup_file.fileno())
            os.replace(temporary, self.backup_path)
            temporary = None
            try:
                mode = self.path.stat().st_mode & 0o777
                os.chmod(self.backup_path, mode)
            except OSError:
                pass
        except OSError as err:
            raise YamlWriteError(f"Sicherung konnte nicht erstellt werden: {err}") from err
        finally:
            if temporary:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass

    def _read_bytes(self) -> bytes:
        try:
            return self.path.read_bytes()
        except FileNotFoundError:
            return b""
        except OSError as err:
            raise YamlStoreError("Entwurf konnte nicht gelesen werden") from err

    def _version_for_bytes(self, content: bytes) -> str | None:
        return hashlib.sha256(content).hexdigest() if content else None

    def load(self) -> YamlSnapshot:
        with self._lock:
            content = self._read_bytes()
            if not content:
                exists = self.path.exists()
                return YamlSnapshot(empty_document(), None, exists, not exists, None if not exists else "Leere YAML-Datei", self._mtime())
            version = self._version_for_bytes(content)
            try:
                loaded = yaml.safe_load(content.decode("utf-8"))
                document = validate_document(loaded)
            except (UnicodeDecodeError, yaml.YAMLError, YamlValidationError) as err:
                return YamlSnapshot(empty_document(), version, True, False, str(err), self._mtime())
            return YamlSnapshot(document, version, True, True, None, self._mtime())

    def _mtime(self) -> str | None:
        try:
            return datetime.fromtimestamp(self.path.stat().st_mtime, tz=UTC).isoformat()
        except FileNotFoundError:
            return None

    def save(self, document: Mapping[str, Any], expected_file_version: str | None) -> YamlSnapshot:
        """Validate and atomically save, refusing stale or invalid overwrites."""
        content = _dump(document)
        with self._lock, self._file_lock():
            current = self._read_bytes()
            current_version = self._version_for_bytes(current)
            if self.path.exists() and not current:
                raise YamlWriteError("Vorhandene leere YAML-Datei wird aus Sicherheitsgründen nicht überschrieben")
            if self.path.exists():
                try:
                    validate_document(yaml.safe_load(current.decode("utf-8")))
                except (UnicodeDecodeError, yaml.YAMLError, YamlValidationError) as err:
                    raise YamlWriteError("Vorhandene ungültige YAML-Datei wird nicht überschrieben") from err
            if current_version != expected_file_version:
                raise YamlVersionConflict("Die YAML-Datei wurde seit der Vorschau verändert")
            if current == content:
                return YamlSnapshot(validate_document(document), current_version, True, True, None, self._mtime())
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._backup_current(current)
            temp_name: str | None = None
            try:
                with tempfile.NamedTemporaryFile("wb", dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp", delete=False) as temp:
                    temp_name = temp.name
                    temp.write(content)
                    temp.flush()
                    os.fsync(temp.fileno())
                os.replace(temp_name, self.path)
                temp_name = None
                try:
                    dir_fd = os.open(self.path.parent, os.O_RDONLY)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                except OSError:
                    # The file replacement is still atomic; directory fsync is
                    # best effort on filesystems that do not expose it.
                    pass
            except OSError as err:
                raise YamlWriteError(str(err)) from err
            finally:
                if temp_name:
                    try:
                        os.unlink(temp_name)
                    except FileNotFoundError:
                        pass
            return YamlSnapshot(validate_document(document), self._version_for_bytes(content), True, True, None, self._mtime())
