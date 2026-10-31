"""Redacted, deterministic migration snapshots.

Snapshots contain logical configuration and fingerprints only.  Pairing keys,
private keys and other secret material are never stored in the snapshot.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .migration_journal import SENSITIVE_WORDS


class SnapshotError(Exception):
    """Snapshot creation or persistence failed."""


class SnapshotCorruptError(SnapshotError):
    """The snapshot cannot be trusted for recovery."""


def _safe_value(key: str, value: Any) -> Any:
    if SENSITIVE_WORDS.search(key):
        return "<redacted>"
    if isinstance(value, Mapping):
        return {str(child_key): _safe_value(str(child_key), child_value) for child_key, child_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_value(key, child) for child in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return f"<{type(value).__name__}>"


def _file_fingerprint(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise SnapshotError(f"Unsichere Snapshot-Datei: {path.name}")
    content = path.read_bytes()
    return {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}


def _snapshot_fingerprint(
    bridge_id: str,
    logical: Mapping[str, Any],
    files: Mapping[str, Mapping[str, Any]],
    secret_fingerprints: Mapping[str, str],
) -> str:
    payload = {
        "bridge_id": bridge_id,
        "files": files,
        "logical": logical,
        "secret_fingerprints": secret_fingerprints,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class MigrationSnapshot:
    transaction_id: str
    bridge_id: str
    logical: Mapping[str, Any]
    files: Mapping[str, Mapping[str, Any]]
    secret_fingerprints: Mapping[str, str]
    fingerprint: str

    @classmethod
    def build(
        cls,
        *,
        transaction_id: str,
        bridge_id: str,
        logical: Mapping[str, Any],
        files: Mapping[str, str | Path] | None = None,
        secret_fingerprints: Mapping[str, bytes] | None = None,
    ) -> MigrationSnapshot:
        safe_logical = {str(key): _safe_value(str(key), value) for key, value in logical.items()}
        file_data = {
            str(relative): _file_fingerprint(Path(path))
            for relative, path in sorted((files or {}).items())
        }
        secret_data = {
            str(name): hashlib.sha256(value).hexdigest()
            for name, value in sorted((secret_fingerprints or {}).items())
        }
        fingerprint = _snapshot_fingerprint(bridge_id, safe_logical, file_data, secret_data)
        return cls(
            transaction_id=transaction_id,
            bridge_id=bridge_id,
            logical=safe_logical,
            files=file_data,
            secret_fingerprints=secret_data,
            fingerprint=fingerprint,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "transaction_id": self.transaction_id,
            "bridge_id": self.bridge_id,
            "logical": self.logical,
            "files": self.files,
            "secret_fingerprints": self.secret_fingerprints,
            "fingerprint": self.fingerprint,
        }


class SnapshotStore:
    """Persist snapshots with the same durability boundary as journals."""

    def __init__(
        self,
        path: str | Path,
        *,
        fault_injector: Callable[[str, Path], None] | None = None,
    ):
        self.path = Path(path)
        self.fault_injector = fault_injector

    def _fault(self, point: str) -> None:
        if self.fault_injector:
            self.fault_injector(point, self.path)

    def load(self) -> MigrationSnapshot | None:
        """Load and integrity-check a snapshot; never repair it implicitly."""
        if self.path.is_symlink():
            raise SnapshotCorruptError("Snapshot darf kein Symlink sein")
        try:
            if self.path.exists() and self.path.stat().st_nlink != 1:
                raise SnapshotCorruptError("Snapshot darf kein Hardlink sein")
            content = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as err:
            raise SnapshotError("Snapshot konnte nicht gelesen werden") from err
        try:
            value = json.loads(content)
        except json.JSONDecodeError as err:
            raise SnapshotCorruptError("Snapshot enthält kein gültiges JSON") from err
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise SnapshotCorruptError("Unbekannte Snapshot-Struktur")
        required = {"transaction_id", "bridge_id", "logical", "files", "secret_fingerprints", "fingerprint"}
        if not required <= value.keys() or not all(
            isinstance(value[key], str) and value[key] for key in ("transaction_id", "bridge_id", "fingerprint")
        ):
            raise SnapshotCorruptError("Unvollständige Snapshot-Identität")
        if not isinstance(value["logical"], dict) or not isinstance(value["files"], dict):
            raise SnapshotCorruptError("Ungültige Snapshot-Nutzdaten")
        if not isinstance(value["secret_fingerprints"], dict):
            raise SnapshotCorruptError("Ungültige Snapshot-Geheimnisprüfsummen")
        for relative, metadata in value["files"].items():
            if not isinstance(relative, str) or not isinstance(metadata, dict):
                raise SnapshotCorruptError("Ungültige Snapshot-Dateiprüfsumme")
            if not isinstance(metadata.get("sha256"), str) or len(metadata["sha256"]) != 64:
                raise SnapshotCorruptError("Ungültige Snapshot-SHA256")
            if type(metadata.get("size")) is not int or metadata["size"] < 0:
                raise SnapshotCorruptError("Ungültige Snapshot-Dateigröße")
        expected = _snapshot_fingerprint(
            value["bridge_id"],
            value["logical"],
            value["files"],
            value["secret_fingerprints"],
        )
        if expected != value["fingerprint"]:
            raise SnapshotCorruptError("Snapshot-Prüfsumme stimmt nicht")
        return MigrationSnapshot(
            transaction_id=value["transaction_id"],
            bridge_id=value["bridge_id"],
            logical=value["logical"],
            files=value["files"],
            secret_fingerprints=value["secret_fingerprints"],
            fingerprint=value["fingerprint"],
        )

    def save(self, snapshot: MigrationSnapshot) -> None:
        payload = json.dumps(snapshot.as_dict(), ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            self._fault("BEFORE_SNAPSHOT_WRITE")
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp", delete=False
            ) as handle:
                temporary = handle.name
                handle.write(payload)
                handle.flush()
                self._fault("DURING_SNAPSHOT_WRITE")
                os.fsync(handle.fileno())
                self._fault("AFTER_SNAPSHOT_WRITE")
            Path(temporary).chmod(0o600)
            self._fault("BEFORE_SNAPSHOT_RENAME")
            os.replace(temporary, self.path)
            temporary = None
            self._fault("AFTER_SNAPSHOT_RENAME")
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            self._fault("AFTER_SNAPSHOT_SYNC")
        except OSError as err:
            raise SnapshotError("Snapshot konnte nicht dauerhaft gespeichert werden") from err
        finally:
            if temporary:
                try:
                    Path(temporary).unlink()
                except FileNotFoundError:
                    pass
