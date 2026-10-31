"""Durable write-ahead records for the isolated native-migration engine.

This module contains no Home Assistant mutation.  It stores only transaction
metadata, fingerprints and redacted diagnostics.  A journal is evidence for
recovery; it is not, by itself, an atomic commit across Core and HAP state.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

JOURNAL_SCHEMA_VERSION = 1
TERMINAL_STATES = frozenset({"COMMITTED", "ROLLED_BACK", "FAILED", "MANUAL_RECOVERY_REQUIRED"})
VALID_STATES = frozenset({
    "PREFLIGHT", "LOCKED", "SNAPSHOT_CREATED", "PREPARED", "QUIESCING",
    "SOURCE_SWITCHING", "RELOADING", "VERIFYING", "ROLLBACK_REQUIRED",
    "ROLLING_BACK", *TERMINAL_STATES,
})
VALID_RECOVERY_STATUSES = frozenset({
    "not_required", "failed_before_native_change", "rollback_required",
    "rollback_failed", "RECOVERY_COMPLETED", "ROLLBACK_COMPLETED",
    "RECOVERY_BLOCKED", "MANUAL_RECOVERY_REQUIRED",
})
SENSITIVE_WORDS = re.compile(r"(?:password|token|secret|pairing|private|pin|key)", re.IGNORECASE)


class JournalError(Exception):
    """Base class for journal failures."""


class JournalCorruptError(JournalError):
    """The journal cannot be trusted for automatic recovery."""


class JournalDurabilityError(JournalError):
    """The journal could not be durably replaced."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _redact_text(value: str | None) -> str | None:
    if value is None:
        return None
    return SENSITIVE_WORDS.sub("<redacted>", value)


def _safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        key_text = str(key)
        if SENSITIVE_WORDS.search(key_text):
            result[key_text] = "<redacted>"
        elif isinstance(item, (str, int, float, bool)) or item is None:
            result[key_text] = item
        else:
            result[key_text] = str(item)
    return result


@dataclass(frozen=True)
class JournalRecord:
    """One durable transaction image."""

    transaction_id: str
    bridge_id: str
    source: str
    target: str
    baseline_fingerprint: str
    config_revision: str
    state: str
    sequence: int = 0
    completed_operations: tuple[str, ...] = ()
    checksums: Mapping[str, str] = field(default_factory=dict)
    recovery_status: str = "not_required"
    error: str | None = None
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

    @classmethod
    def new(
        cls,
        *,
        bridge_id: str,
        source: str,
        target: str,
        baseline_fingerprint: str,
        config_revision: str,
    ) -> JournalRecord:
        return cls(
            transaction_id=str(uuid4()),
            bridge_id=bridge_id,
            source=source,
            target=target,
            baseline_fingerprint=baseline_fingerprint,
            config_revision=config_revision,
            state="PREFLIGHT",
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "transaction_id": self.transaction_id,
            "bridge_id": self.bridge_id,
            "source": self.source,
            "target": self.target,
            "baseline_fingerprint": self.baseline_fingerprint,
            "config_revision": self.config_revision,
            "state": self.state,
            "sequence": self.sequence,
            "completed_operations": list(self.completed_operations),
            "checksums": dict(sorted(self.checksums.items())),
            "recovery_status": self.recovery_status,
            "error": _redact_text(self.error),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> JournalRecord:
        if value.get("schema_version") != JOURNAL_SCHEMA_VERSION:
            raise JournalCorruptError("Unbekannte Journal-Version")
        required = (
            "transaction_id",
            "bridge_id",
            "source",
            "target",
            "baseline_fingerprint",
            "config_revision",
            "state",
            "sequence",
            "completed_operations",
            "checksums",
            "recovery_status",
            "created_at",
            "updated_at",
        )
        if any(key not in value for key in required):
            raise JournalCorruptError("Unvollständige Journal-Struktur")
        if not all(isinstance(value.get(key), str) and value.get(key) for key in required[:7]):
            raise JournalCorruptError("Ungültige Journal-Identität")
        if value["source"] not in {"user", "import"} or value["target"] not in {"user", "import"}:
            raise JournalCorruptError("Ungültige HomeKit-Quelle im Journal")
        if value["state"] not in VALID_STATES:
            raise JournalCorruptError("Unbekannter Journal-Zustand")
        operations = value["completed_operations"]
        checksums = value["checksums"]
        if not isinstance(operations, list) or not all(isinstance(item, str) for item in operations):
            raise JournalCorruptError("Ungültige abgeschlossene Operationen")
        if not isinstance(checksums, dict) or not all(
            isinstance(key, str) and isinstance(item, str) for key, item in checksums.items()
        ):
            raise JournalCorruptError("Ungültige Prüfsummen")
        if type(value["sequence"]) is not int or value["sequence"] < 0:
            raise JournalCorruptError("Ungültige Journal-Sequenz")
        error = value.get("error")
        if error is not None and not isinstance(error, str):
            raise JournalCorruptError("Ungültige Fehlerdiagnose")
        if not isinstance(value["recovery_status"], str) or value["recovery_status"] not in VALID_RECOVERY_STATUSES:
            raise JournalCorruptError("Unbekannter Recovery-Status")
        if not all(isinstance(value.get(key), str) and value[key] for key in ("created_at", "updated_at")):
            raise JournalCorruptError("Ungültige Journal-Zeitstempel")
        return cls(
            transaction_id=value["transaction_id"],
            bridge_id=value["bridge_id"],
            source=value["source"],
            target=value["target"],
            baseline_fingerprint=value["baseline_fingerprint"],
            config_revision=value["config_revision"],
            state=value["state"],
            sequence=value["sequence"],
            completed_operations=tuple(operations),
            checksums=checksums,
            recovery_status=value["recovery_status"],
            error=error,
            created_at=value["created_at"],
            updated_at=value["updated_at"],
        )

    def advance(
        self,
        *,
        state: str,
        completed_operation: str | None = None,
        checksums: Mapping[str, str] | None = None,
        recovery_status: str | None = None,
        error: str | None = None,
    ) -> JournalRecord:
        operations = list(self.completed_operations)
        if completed_operation and completed_operation not in operations:
            operations.append(completed_operation)
        merged = dict(self.checksums)
        if checksums:
            merged.update(checksums)
        return JournalRecord(
            transaction_id=self.transaction_id,
            bridge_id=self.bridge_id,
            source=self.source,
            target=self.target,
            baseline_fingerprint=self.baseline_fingerprint,
            config_revision=self.config_revision,
            state=state,
            sequence=self.sequence + 1,
            completed_operations=tuple(operations),
            checksums=merged,
            recovery_status=recovery_status or self.recovery_status,
            error=self.error if error is None else error,
            created_at=self.created_at,
            updated_at=_utc_now(),
        )


def canonical_fingerprint(value: Mapping[str, Any]) -> str:
    """Hash safe JSON metadata deterministically."""
    encoded = json.dumps(_safe_mapping(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class JournalStore:
    """Atomically persist and recover one journal image."""

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

    def load(self) -> JournalRecord | None:
        if self.path.is_symlink():
            raise JournalCorruptError("Journal darf kein Symlink sein")
        try:
            if self.path.exists() and self.path.stat().st_nlink != 1:
                raise JournalCorruptError("Journal darf kein Hardlink sein")
        except OSError as err:
            raise JournalError("Journal-Metadaten konnten nicht gelesen werden") from err
        try:
            content = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as err:
            raise JournalError("Journal konnte nicht gelesen werden") from err
        try:
            value = json.loads(content)
        except json.JSONDecodeError as err:
            raise JournalCorruptError("Journal enthält kein gültiges JSON") from err
        if not isinstance(value, dict):
            raise JournalCorruptError("Journal ist kein Objekt")
        return JournalRecord.from_dict(value)

    def save(self, record: JournalRecord) -> JournalRecord:
        existing = self.load()
        if existing and existing.state not in TERMINAL_STATES:
            if record.transaction_id != existing.transaction_id:
                raise JournalError("Aktive Journal-Transaktion darf nicht ersetzt werden")
            if record.sequence <= existing.sequence:
                raise JournalError("Journal-Sequenz muss monoton steigen")
        payload = json.dumps(record.as_dict(), ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            self._fault("BEFORE_JOURNAL_WRITE")
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = handle.name
                handle.write(payload)
                handle.flush()
                self._fault("DURING_JOURNAL_WRITE")
                os.fsync(handle.fileno())
                self._fault("AFTER_JOURNAL_WRITE")
            Path(temporary).chmod(0o600)
            self._fault("BEFORE_JOURNAL_RENAME")
            os.replace(temporary, self.path)
            temporary = None
            self._fault("AFTER_JOURNAL_RENAME")
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            self._fault("AFTER_JOURNAL_SYNC")
        except OSError as err:
            raise JournalDurabilityError("Journal konnte nicht dauerhaft gespeichert werden") from err
        finally:
            if temporary:
                try:
                    Path(temporary).unlink()
                except FileNotFoundError:
                    pass
        return record
