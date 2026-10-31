"""Redacted, deterministic migration snapshots.

Snapshots contain logical configuration and fingerprints only.  Pairing keys,
private keys and other secret material are never stored in the snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from .migration_journal import SENSITIVE_WORDS


class SnapshotError(Exception):
    """Snapshot creation or persistence failed."""


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
    ) -> "MigrationSnapshot":
        safe_logical = {str(key): _safe_value(str(key), value) for key, value in logical.items()}
        file_data = {
            str(relative): _file_fingerprint(Path(path))
            for relative, path in sorted((files or {}).items())
        }
        secret_data = {
            str(name): hashlib.sha256(value).hexdigest()
            for name, value in sorted((secret_fingerprints or {}).items())
        }
        payload = {
            "bridge_id": bridge_id,
            "files": file_data,
            "logical": safe_logical,
            "secret_fingerprints": secret_data,
        }
        fingerprint = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
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

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def save(self, snapshot: MigrationSnapshot) -> None:
        payload = json.dumps(snapshot.as_dict(), ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp", delete=False
            ) as handle:
                temporary = handle.name
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            Path(temporary).chmod(0o600)
            os.replace(temporary, self.path)
            temporary = None
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as err:
            raise SnapshotError("Snapshot konnte nicht dauerhaft gespeichert werden") from err
        finally:
            if temporary:
                try:
                    Path(temporary).unlink()
                except FileNotFoundError:
                    pass
