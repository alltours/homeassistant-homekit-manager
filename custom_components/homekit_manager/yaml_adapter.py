"""Conservative HomeKit YAML editor for proven direct or included sources.

Only plain ``homekit:`` in ``configuration.yaml`` or a direct
``homekit: !include <single file>`` is editable. Other includes and packages
remain read-only. Production use requires a separate local write grant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import ctypes
import errno
import fcntl
from hashlib import sha256
from io import StringIO
import asyncio
import json
import os
from pathlib import Path
import re
import stat
import sys
import threading
import uuid
from types import SimpleNamespace
from typing import Any, Callable, Mapping

from ruamel.yaml import YAML

from .safety import has_extended_acl

class YamlAdapterBlocked(ValueError):
    """The source, structure, or requested change is not provably safe."""


class YamlAdapterConflict(YamlAdapterBlocked):
    """The file differs from the bytes used to construct the plan."""


class YamlActivationUnknown(YamlAdapterBlocked):
    """The file was written, but Core activation has an unknown outcome."""


@dataclass(frozen=True)
class YamlFilterPlan:
    operation_id: str
    entry_id: str
    source_path: Path
    source_revision: str
    target_revision: str
    bridge_name: str
    bridge_port: int
    before_filter: Mapping[str, Any]
    after_filter: Mapping[str, Any]
    before_bytes: bytes = field(repr=False)
    after_bytes: bytes = field(repr=False)


@dataclass(frozen=True)
class YamlApplyResult:
    operation_id: str
    state: str
    backup_path: Path
    source_revision: str
    target_revision: str


_DIRECT_INCLUDE = re.compile(r"^homekit:\s*!include\s+([A-Za-z0-9_.-]+)(?:\s*#.*)?$", re.MULTILINE)
_DIRECT_VALUE = re.compile(r"^homekit:\s*(?:#.*)?$", re.MULTILINE)
_HOMEKIT_KEY = re.compile(r"^homekit\s*:", re.MULTILINE)
_FILTER_KEYS = frozenset({"include_entities", "exclude_entities", "include_domains", "exclude_domains", "include_entity_globs", "exclude_entity_globs"})
_APPLY_LOCKS: dict[Path, threading.Lock] = {}


def _yaml() -> YAML:
    parser = YAML(typ="rt")
    parser.allow_duplicate_keys = False
    parser.preserve_quotes = True
    return parser


def _assert_plain(node: Any) -> None:
    """Reject tags, aliases, anchors, merges and secrets before editing."""
    if getattr(node, "anchor", None) is not None and node.anchor.value:
        raise YamlAdapterBlocked("YAML-Anker oder Aliase sind schreibgeschützt")
    tag = getattr(node, "tag", None)
    if tag is not None and getattr(tag, "value", None) is not None and not str(tag).startswith("tag:yaml.org,2002:"):
        raise YamlAdapterBlocked("YAML-Tags einschließlich !secret sind schreibgeschützt")
    if isinstance(node, Mapping):
        if getattr(node, "merge", None):
            raise YamlAdapterBlocked("YAML-Merge-Keys sind schreibgeschützt")
        for key, value in node.items():
            _assert_plain(key)
            _assert_plain(value)
    elif isinstance(node, list):
        for item in node:
            _assert_plain(item)


def _plain(node: Any) -> Any:
    if isinstance(node, Mapping):
        return {str(key): _plain(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_plain(value) for value in node]
    return node


def _has_comments(node: Any) -> bool:
    ca = getattr(node, "ca", None)
    if ca is not None and (ca.comment or ca.end or ca.items):
        return True
    if isinstance(node, Mapping):
        return any(_has_comments(value) for value in node.values())
    if isinstance(node, list):
        return any(_has_comments(value) for value in node)
    return False


def _dump(parser: YAML, node: Any) -> bytes:
    stream = StringIO()
    parser.dump(node, stream)
    return stream.getvalue().encode("utf-8")


def _read_regular(path: Path) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as err:
        if err.errno == errno.ELOOP:
            raise YamlAdapterBlocked("HomeKit-Quelldatei ist ein Symlink und bleibt schreibgeschützt") from err
        raise
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 4 * 1024 * 1024:
            raise YamlAdapterBlocked("Quelle ist keine reguläre HomeKit-Datei bis 4 MiB")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(descriptor)


def _digest(content: bytes) -> str:
    return sha256(content).hexdigest()


def _extended_attribute_names(path: Path) -> set[str]:
    if hasattr(os, "listxattr"):
        return set(os.listxattr(path, follow_symlinks=False))
    if sys.platform == "darwin":
        # This Python build omits os.listxattr, although macOS exposes it.
        # XATTR_NOFOLLOW prevents a swapped symlink from being traversed.
        libc = ctypes.CDLL(None, use_errno=True)
        listxattr = libc.listxattr
        listxattr.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
        listxattr.restype = ctypes.c_ssize_t
        size = listxattr(os.fsencode(path), None, 0, 0x0001)
        if size < 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), path)
        if size == 0:
            return set()
        buffer = ctypes.create_string_buffer(size)
        actual = listxattr(os.fsencode(path), buffer, size, 0x0001)
        if actual < 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), path)
        return {os.fsdecode(name) for name in buffer.raw[:actual].split(b"\0") if name}
    raise OSError(errno.ENOTSUP, "Erweiterte Dateiattribute sind nicht prüfbar", path)


def _writable_metadata(path: Path) -> tuple[int, int, int, int, int]:
    """Reject replacement that would silently change owner, group or file type."""
    info = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise YamlAdapterBlocked("HomeKit-Quelldatei ist kein eindeutiger regulärer Dateiknoten")
    if info.st_uid != os.geteuid() or info.st_gid != os.getegid():
        raise YamlAdapterBlocked("Dateibesitz würde beim atomaren Ersatz verändert")
    mode = stat.S_IMODE(info.st_mode)
    if not mode & stat.S_IWUSR or mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise YamlAdapterBlocked("HomeKit-Quelldatei ist schreibgeschützt oder für andere Benutzer schreibbar")
    if info.st_mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX):
        raise YamlAdapterBlocked("Sonderberechtigungen der Quelldatei sind nicht sicher ersetzbar")
    if getattr(info, "st_flags", 0):
        raise YamlAdapterBlocked("Dateisystem-Flags der Quelldatei sind nicht sicher ersetzbar")
    try:
        # macOS automatically adds com.apple.provenance to newly created files,
        # including our replacement. Other attributes need an explicit copier.
        if _extended_attribute_names(path) - {"com.apple.provenance"}:
            raise YamlAdapterBlocked("Erweiterte Dateiattribute sind nicht sicher ersetzbar")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                raise YamlAdapterBlocked("HomeKit-Quelldatei wurde während der Berechtigungsprüfung ersetzt")
            if has_extended_acl(descriptor):
                raise YamlAdapterBlocked("HomeKit-Quelldatei mit ACL bleibt schreibgeschützt")
        finally:
            os.close(descriptor)
    except OSError as err:
        raise YamlAdapterBlocked("Dateiattribute der Quelldatei konnten nicht geprüft werden") from err
    return info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid


def _sync_dir(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class YamlHomeKitAdapter:
    """Plan, atomically edit and restore one unambiguous YAML include."""

    def __init__(self, config_dir: str | Path):
        self.root = Path(config_dir).resolve(strict=True)

    def _backup_dir(self) -> Path:
        storage = self.root / ".storage"
        if storage.is_symlink():
            raise YamlAdapterBlocked(".storage-Symlink ist nicht als Backup-Ziel zulässig")
        storage.mkdir(mode=0o700, exist_ok=True)
        storage_info = storage.stat(follow_symlinks=False)
        if (not stat.S_ISDIR(storage_info.st_mode) or storage_info.st_uid != os.geteuid()
                or stat.S_IMODE(storage_info.st_mode) & 0o022):
            raise YamlAdapterBlocked("HomeKit-Backup-Verzeichnis hat unsicheren Besitzer oder Berechtigungen")
        storage_fd = os.open(storage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            opened = os.fstat(storage_fd)
            if ((opened.st_dev, opened.st_ino) != (storage_info.st_dev, storage_info.st_ino)
                    or has_extended_acl(storage_fd)):
                raise YamlAdapterBlocked("HomeKit-Backup-Verzeichnis hat eine ACL oder wurde ersetzt")
        finally:
            os.close(storage_fd)
        backup_dir = self.root / ".storage" / "homekit_manager_backups"
        backup_dir.mkdir(mode=0o700, exist_ok=True)
        for directory, private in ((storage, False), (backup_dir, True)):
            info = directory.stat(follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
                raise YamlAdapterBlocked("HomeKit-Backup-Verzeichnis hat unsicheren Besitzer oder Dateityp")
            mode = stat.S_IMODE(info.st_mode)
            if mode & 0o022 or (private and mode != 0o700):
                raise YamlAdapterBlocked("HomeKit-Backup-Verzeichnis hat unsichere Berechtigungen")
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                opened = os.fstat(descriptor)
                if ((opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
                        or has_extended_acl(descriptor)):
                    raise YamlAdapterBlocked("HomeKit-Backup-Verzeichnis hat eine ACL oder wurde ersetzt")
            finally:
                os.close(descriptor)
        return backup_dir

    def _record(self, plan: YamlFilterPlan, state: str) -> None:
        """Durable metadata only; never journal YAML values or secrets."""
        directory = self._backup_dir()
        item = {"operation_id": plan.operation_id, "entry_id": plan.entry_id,
                "source_revision": plan.source_revision, "target_revision": plan.target_revision,
                "state": state}
        content = (json.dumps(item, sort_keys=True) + "\n").encode()
        journal = directory / "journal.jsonl"
        descriptor = os.open(journal, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600
                    or has_extended_acl(descriptor)):
                raise YamlAdapterBlocked("HomeKit-Journal ist keine private reguläre Datei")
            if os.write(descriptor, content) != len(content):
                raise OSError("Audit-Journal wurde nur teilweise geschrieben")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        _sync_dir(directory)

    def operation_state(self, plan: YamlFilterPlan) -> str:
        """Reconcile file bytes after a crash; this method never writes."""
        current = _digest(_read_regular(plan.source_path))
        if current == plan.target_revision:
            return "verified_file"
        if current == plan.source_revision:
            return "not_applied"
        return "unknown_outcome"

    def current_revision(self) -> tuple[str, str]:
        """Read proven source name and bytes without modifying a file."""
        path = self._source_path()
        return path.name, _digest(_read_regular(path))

    async def async_apply_with_core(self, hass: Any, entry: Any, plan: YamlFilterPlan, *, isolated_authority: bool = False, production_grant: Any = None, timeout: float = 30.0) -> YamlApplyResult:
        """Apply and verify in isolation using Core's actual YAML reload.

        Core 2026.10.4 reloads *all* HomeKit entries for homekit.reload.  This
        path therefore refuses mixed native/YAML installations even in tests.
        """
        if not isolated_authority and production_grant is None:
            raise YamlAdapterBlocked("Produktiver HomeKit-YAML-Writer ist gesperrt")
        if production_grant is not None:
            await production_grant.verify(hass, plan.entry_id, "import")
        from homeassistant.const import __version__
        from homeassistant.config_entries import SOURCE_IMPORT
        if __version__ != "2026.10.4" or entry.source != SOURCE_IMPORT or entry.entry_id != plan.entry_id:
            raise YamlAdapterBlocked("Core-Version, Quelle oder Entry weicht vom Plan ab")
        if (dict(entry.data) | dict(getattr(entry, "options", {}))).get("mode", "bridge") != "bridge":
            raise YamlAdapterBlocked("Nur HomeKit-Entries im Bridge-Modus dürfen geändert werden")
        all_entries = hass.config_entries.async_entries("homekit")
        if not all_entries or any(item.source != SOURCE_IMPORT for item in all_entries):
            raise YamlAdapterBlocked("Core-Reload würde auch native HomeKit-Entries betreffen")
        if not any(item.entry_id == plan.entry_id for item in all_entries):
            raise YamlAdapterBlocked("Ziel-Entry ist nicht mehr vorhanden")
        if production_grant is not None:
            await production_grant.verify(hass, plan.entry_id, "import")
        def write_with_grant_check():
            if production_grant is not None:
                production_grant.verify_sync(hass, plan.entry_id, "import")
            return self.apply(plan, expected_revision=plan.source_revision,
                              isolated_authority=True,
                              pre_commit_check=(lambda: production_grant.verify_sync(
                                  hass, plan.entry_id, "import")) if production_grant is not None else None)
        result = await hass.async_add_executor_job(write_with_grant_check)
        try:
            from homeassistant.config import async_hass_config_yaml
            parsed = await async_hass_config_yaml(hass)
            if "homekit" not in parsed:
                raise YamlAdapterBlocked("HomeKit-Konfiguration ist nach Apply nicht mehr lesbar")
            await asyncio.wait_for(hass.services.async_call("homekit", "reload", blocking=True), timeout)
            await asyncio.wait_for(hass.async_block_till_done(), timeout)
            observed = hass.config_entries.async_get_entry(plan.entry_id)
            if observed is None or observed.source != SOURCE_IMPORT or observed.state.value != "loaded":
                raise YamlAdapterBlocked("Importierter HomeKit-Entry ist nach Reload nicht geladen")
            observed_filter = observed.options.get("filter")
            if not isinstance(observed_filter, Mapping) or any(
                observed_filter.get(key, []) != value for key, value in plan.after_filter.items()
            ):
                raise YamlAdapterBlocked("Core-Optionen stimmen nicht mit dem YAML-Plan überein")
            await hass.async_add_executor_job(lambda: self._record(plan, "verified_core"))
        except Exception as err:
            await hass.async_add_executor_job(lambda: self._record(plan, "unknown_outcome"))
            raise YamlActivationUnknown("YAML-Datei gespeichert; Core-Aktivierung ungeklärt. Kein automatischer Retry.") from err
        return YamlApplyResult(result.operation_id, "verified_core", result.backup_path, result.source_revision, result.target_revision)

    def _source_path(self) -> Path:
        root_file = self.root / "configuration.yaml"
        root_bytes = _read_regular(root_file)
        try:
            root_text = root_bytes.decode("utf-8")
        except UnicodeDecodeError as err:
            raise YamlAdapterBlocked("configuration.yaml ist nicht UTF-8") from err
        matches = _DIRECT_INCLUDE.findall(root_text)
        if len(_HOMEKIT_KEY.findall(root_text)) != 1 or re.search(r"(?m)^\s*packages\s*:", root_text):
            raise YamlAdapterBlocked("HomeKit-YAML-Provenienz ist nicht eindeutig nachgewiesen")
        if not matches and len(_DIRECT_VALUE.findall(root_text)) == 1:
            return root_file
        if len(matches) != 1:
            raise YamlAdapterBlocked("HomeKit-YAML-Provenienz ist weder direkt noch als einzelner Include nachgewiesen")
        name = matches[0]
        if name in {".", ".."}:
            raise YamlAdapterBlocked("Ungültiger Include-Pfad")
        path = self.root / name
        if path.is_symlink() or path.resolve(strict=True).parent != self.root:
            raise YamlAdapterBlocked("Include-Symlinks oder externe Pfade sind nicht editierbar")
        return path

    def _parse(self, path: Path, content: bytes) -> tuple[YAML, Any, list[Any]]:
        try:
            parser = _yaml()
            direct = path == self.root / "configuration.yaml"
            if direct and re.search(rb"(?m)^  - ", content):
                # Common Home Assistant list indentation. Other styles remain
                # supported only if ruamel reproduces the original bytes.
                parser.indent(mapping=2, sequence=4, offset=2)
            node = parser.load(content.decode("utf-8"))
            _assert_plain(node)
        except YamlAdapterBlocked:
            raise
        except Exception as err:
            raise YamlAdapterBlocked("HomeKit-Include ist nicht sicher parsebar") from err
        value = node.get("homekit") if direct and isinstance(node, Mapping) else node
        if isinstance(value, Mapping):
            bridges = [value]
        elif isinstance(value, list) and all(isinstance(item, Mapping) for item in value):
            bridges = value
        else:
            raise YamlAdapterBlocked("HomeKit-Quelle muss eine Bridge oder eine Bridge-Liste enthalten")
        if _dump(parser, node) != content:
            raise YamlAdapterBlocked("YAML-Roundtrip verändert unberührte Formatierung")
        return parser, node, bridges

    def plan_filter(self, entry: Any, new_filter: Mapping[str, Any]) -> YamlFilterPlan:
        from homeassistant.components.homekit import CONFIG_SCHEMA
        from homeassistant.config_entries import SOURCE_IMPORT

        if getattr(entry, "domain", None) != "homekit" or getattr(entry, "source", None) != SOURCE_IMPORT:
            raise YamlAdapterBlocked("Nur importierte HomeKit-Config-Entries sind YAML-Quellen")
        if (dict(entry.data) | dict(getattr(entry, "options", {}))).get("mode", "bridge") != "bridge":
            raise YamlAdapterBlocked("Nur HomeKit-Entries im Bridge-Modus dürfen geändert werden")
        entry_id = getattr(entry, "entry_id", None)
        bridge_name = entry.data.get("name")
        bridge_port = entry.data.get("port")
        if not isinstance(bridge_name, str) or not isinstance(bridge_port, int):
            raise YamlAdapterBlocked("Name und Port des importierten Entries müssen bekannt sein")

        path = self._source_path()
        before = _read_regular(path)
        parser, node, bridges = self._parse(path, before)
        matches = [item for item in bridges if item.get("name") == bridge_name and item.get("port") == bridge_port]
        if len(matches) != 1 or not entry_id:
            raise YamlAdapterBlocked("Importierter Config Entry passt nicht eindeutig zu Name und Port")
        if set(new_filter) - _FILTER_KEYS or any(not isinstance(value, list) or any(not isinstance(entry, str) for entry in value) for value in new_filter.values()):
            raise YamlAdapterBlocked("Nur HomeKit-Filterlisten sind schreibbar")
        target = matches[0]
        if target.get("mode", "bridge") != "bridge":
            raise YamlAdapterBlocked("YAML-Accessory-Modus bleibt schreibgeschützt")
        old_filter = _plain(target.get("filter", {}))
        if not isinstance(old_filter, Mapping) or set(old_filter) - _FILTER_KEYS:
            raise YamlAdapterBlocked("Unbekannte Filterfelder bleiben schreibgeschützt")
        if _has_comments(target.get("filter", {})) or getattr(target, "ca", None) and target.ca.items.get("filter"):
            raise YamlAdapterBlocked("Kommentare im zu ersetzenden Filter bleiben schreibgeschützt")
        target["filter"] = dict(new_filter)
        # Core 2026.10.4 validates the complete effective HomeKit configuration.
        try:
            CONFIG_SCHEMA({"homekit": [_plain(item) for item in bridges]})
        except Exception as err:
            raise YamlAdapterBlocked("HomeKit-Core-Schema lehnt den Änderungsplan ab") from err
        after = _dump(parser, node)
        if after == before:
            raise YamlAdapterBlocked("Keine Änderung")
        return YamlFilterPlan(uuid.uuid4().hex, entry_id, path, _digest(before), _digest(after), bridge_name, bridge_port, old_filter, dict(new_filter), before, after)

    def apply(self, plan: YamlFilterPlan, *, expected_revision: str, isolated_authority: bool = False,
              pre_commit_check: Callable[[], None] | None = None) -> YamlApplyResult:
        """Apply only in an explicit isolated harness; production API has no route here."""
        if not isolated_authority:
            raise YamlAdapterBlocked("Produktiver HomeKit-YAML-Writer ist gesperrt")
        lock = _APPLY_LOCKS.setdefault(plan.source_path, threading.Lock())
        with lock:
            if self._source_path() != plan.source_path:
                raise YamlAdapterConflict("HomeKit-Quelldatei wurde gewechselt")
            try:
                descriptor = os.open(plan.source_path, os.O_RDONLY | os.O_NOFOLLOW)
            except OSError as err:
                if err.errno == errno.ELOOP:
                    raise YamlAdapterBlocked("HomeKit-Quelldatei ist ein Symlink") from err
                raise
            try:
                # Cooperative cross-process lock on the source inode. The
                # revision and inode checks still run after acquisition.
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                locked = os.fstat(descriptor)
                if (locked.st_dev, locked.st_ino) != _writable_metadata(plan.source_path)[:2]:
                    raise YamlAdapterConflict("YAML-Dateiknoten wurde vor der Sperre ersetzt")
                return self._apply_locked(plan, expected_revision, pre_commit_check)
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def _apply_locked(self, plan: YamlFilterPlan, expected_revision: str,
                      pre_commit_check: Callable[[], None] | None) -> YamlApplyResult:
        if self._source_path() != plan.source_path or expected_revision != plan.source_revision:
            raise YamlAdapterConflict("Quelle oder Revision weicht vom Plan ab")
        source_metadata = _writable_metadata(plan.source_path)
        current = _read_regular(plan.source_path)
        if _digest(current) != plan.source_revision or current != plan.before_bytes:
            raise YamlAdapterConflict("YAML-Datei hat sich seit der Vorschau geändert")
        # Verify both byte images and the precise semantic scope again.  A
        # forged or stale plan must not edit another bridge or unknown field.
        _, old_node, old_bridges = self._parse(plan.source_path, current)
        _, new_node, new_bridges = self._parse(plan.source_path, plan.after_bytes)
        if len(old_bridges) != len(new_bridges) or _digest(plan.after_bytes) != plan.target_revision:
            raise YamlAdapterBlocked("Planinhalt oder Zielrevision ist ungültig")
        if sum(item.get("name") == plan.bridge_name and item.get("port") == plan.bridge_port for item in old_bridges) != 1:
            raise YamlAdapterBlocked("Ziel-Bridge ist nicht mehr eindeutig")
        if plan.source_path == self.root / "configuration.yaml":
            old_outer, new_outer = _plain(old_node), _plain(new_node)
            old_outer.pop("homekit")
            new_outer.pop("homekit")
            if old_outer != new_outer:
                raise YamlAdapterBlocked("Änderungsplan verändert andere configuration.yaml-Werte")
        for old_item, new_item in zip(old_bridges, new_bridges, strict=True):
            old_value, new_value = _plain(old_item), _plain(new_item)
            if old_value.get("name") == plan.bridge_name and old_value.get("port") == plan.bridge_port:
                if old_value.get("filter", {}) != dict(plan.before_filter) or new_value.get("filter", {}) != dict(plan.after_filter):
                    raise YamlAdapterBlocked("Filterplan stimmt nicht mit den Dateiwerten überein")
                old_value.pop("filter", None)
                new_value.pop("filter", None)
            if old_value != new_value:
                raise YamlAdapterBlocked("Änderungsplan verändert unbeteiligte YAML-Felder")
        from homeassistant.components.homekit import CONFIG_SCHEMA
        try:
            CONFIG_SCHEMA({"homekit": [_plain(item) for item in new_bridges]})
        except Exception as err:
            raise YamlAdapterBlocked("HomeKit-Core-Schema lehnt den Apply-Inhalt ab") from err
        # Re-render from the just-verified source so a forged plan cannot
        # alter comments, unrelated integrations, or whitespace outside the
        # exact supported filter edit even if the parsed values are equal.
        regenerated = self.plan_filter(
            SimpleNamespace(domain="homekit", source="import", entry_id=plan.entry_id,
                            data={"name": plan.bridge_name, "port": plan.bridge_port}),
            plan.after_filter,
        )
        if regenerated.after_bytes != plan.after_bytes or regenerated.before_filter != plan.before_filter:
            raise YamlAdapterBlocked("Änderungsplan verändert unbeteiligte YAML-Bytes")
        backup_dir = self._backup_dir()
        backup = backup_dir / f"{plan.operation_id}.yaml"
        descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(current)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            backup.unlink(missing_ok=True)
            raise
        if _digest(backup.read_bytes()) != plan.source_revision:
            raise YamlAdapterBlocked("Backup-Integrität konnte nicht bestätigt werden")
        _sync_dir(backup_dir)
        self._record(plan, "applying")
        temporary = plan.source_path.with_name(f".{plan.source_path.name}.{plan.operation_id}.tmp")
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(plan.after_bytes)
                stream.flush()
                os.fchmod(stream.fileno(), stat.S_IMODE(source_metadata[2]))
                os.fsync(stream.fileno())
            if _writable_metadata(plan.source_path) != source_metadata:
                raise YamlAdapterConflict("YAML-Dateiknoten wurde während Apply ersetzt")
            if _digest(_read_regular(plan.source_path)) != plan.source_revision:
                raise YamlAdapterConflict("YAML-Datei wurde während Apply geändert")
            # No await or executor handoff separates this grant recheck from
            # the atomic source replacement. Revocation during backup/parse
            # must still prevent changing the HomeKit source.
            if pre_commit_check is not None:
                pre_commit_check()
            os.replace(temporary, plan.source_path)
            _sync_dir(plan.source_path.parent)
        finally:
            temporary.unlink(missing_ok=True)
        if _digest(_read_regular(plan.source_path)) != plan.target_revision:
            raise YamlAdapterBlocked("Nachverifikation fehlgeschlagen; Ergebnis unbekannt")
        self._record(plan, "verified_file")
        return YamlApplyResult(plan.operation_id, "verified_file", backup, plan.source_revision, plan.target_revision)

    def recover(self, result: YamlApplyResult, *, isolated_authority: bool = False) -> str:
        """Restore only if the current file still equals this exact operation."""
        if not isolated_authority:
            raise YamlAdapterBlocked("Produktive Wiederherstellung ist gesperrt")
        source = self._source_path()
        lock = _APPLY_LOCKS.setdefault(source, threading.Lock())
        with lock:
            descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                locked = os.fstat(descriptor)
                if (locked.st_dev, locked.st_ino) != _writable_metadata(source)[:2]:
                    raise YamlAdapterConflict("YAML-Dateiknoten wurde vor Restore ersetzt")
                return self._recover_locked(result, source)
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def _recover_locked(self, result: YamlApplyResult, source: Path) -> str:
        source_metadata = _writable_metadata(source)
        if _digest(_read_regular(source)) != result.target_revision:
            raise YamlAdapterConflict("Aktuelle Datei ist nicht das Ergebnis dieses Apply")
        backup = result.backup_path
        if backup.parent != self.root / ".storage" / "homekit_manager_backups":
            raise YamlAdapterBlocked("Backup liegt außerhalb des vorgesehenen Verzeichnisses")
        old = _read_regular(backup)
        if _digest(old) != result.source_revision:
            raise YamlAdapterBlocked("Backup-Integrität fehlgeschlagen")
        temporary = source.with_name(f".{source.name}.{result.operation_id}.restore")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(old)
                stream.flush()
                os.fchmod(stream.fileno(), stat.S_IMODE(source_metadata[2]))
                os.fsync(stream.fileno())
            if _writable_metadata(source) != source_metadata:
                raise YamlAdapterConflict("YAML-Dateiknoten wurde während Restore ersetzt")
            if _digest(_read_regular(source)) != result.target_revision:
                raise YamlAdapterConflict("Datei wurde während Restore geändert")
            os.replace(temporary, source)
            _sync_dir(source.parent)
        finally:
            temporary.unlink(missing_ok=True)
        if _digest(_read_regular(source)) != result.source_revision:
            raise YamlAdapterBlocked("Restore-Nachverifikation fehlgeschlagen")
        return "verified_file_restore"
