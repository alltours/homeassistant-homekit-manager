"""Persistence integrity and deterministic fault-injection tests for 0.10.16."""
from __future__ import annotations

import errno
import json
from pathlib import Path

import pytest

from custom_components.homekit_manager.migration_journal import (
    JournalCorruptError,
    JournalDurabilityError,
    JournalRecord,
    JournalStore,
)
from custom_components.homekit_manager.migration_snapshot import (
    MigrationSnapshot,
    SnapshotCorruptError,
    SnapshotStore,
)


def _record() -> JournalRecord:
    return JournalRecord.new(
        bridge_id="bridge-a",
        source="user",
        target="import",
        baseline_fingerprint="baseline",
        config_revision="revision",
    )


def _snapshot(tmp_path: Path) -> MigrationSnapshot:
    source = tmp_path / "configuration.yaml"
    source.write_text("homekit: []\n", encoding="utf-8")
    return MigrationSnapshot.build(
        transaction_id="transaction-1",
        bridge_id="bridge-a",
        logical={"entry_id": "bridge-a", "mac": "AA:BB:CC:DD:EE:FF"},
        files={"configuration.yaml": source},
    )


def test_snapshot_round_trip_validates_its_own_fingerprint(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.json"
    store = SnapshotStore(path)
    original = _snapshot(tmp_path)
    store.save(original)
    loaded = store.load()
    assert loaded == original

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["logical"]["mac"] = "00:00:00:00:00:00"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SnapshotCorruptError, match="Prüfsumme"):
        store.load()


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("", "gültiges JSON"),
        ("{broken", "gültiges JSON"),
        (json.dumps({"schema_version": 1}), "Snapshot-Struktur"),
    ],
)
def test_corrupt_snapshot_is_fail_closed(tmp_path: Path, content: str, message: str) -> None:
    path = tmp_path / "snapshot.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(SnapshotCorruptError, match=message if message != "Snapshot-Struktur" else "(Struktur|Identität)"):
        SnapshotStore(path).load()


def test_journal_rejects_unknown_state_and_recovery_status(tmp_path: Path) -> None:
    path = tmp_path / "journal.json"
    store = JournalStore(path)
    store.save(_record())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["state"] = "MADE_UP_STATE"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(JournalCorruptError, match="Journal-Zustand"):
        store.load()

    path.unlink()
    store.save(_record())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["recovery_status"] = "MADE_UP_STATUS"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(JournalCorruptError, match="Recovery-Status"):
        store.load()


@pytest.mark.parametrize(
    ("point", "error"),
    [
        ("BEFORE_JOURNAL_WRITE", OSError(errno.ENOSPC, "no space")),
        ("DURING_JOURNAL_WRITE", OSError(errno.EIO, "io error")),
        ("AFTER_JOURNAL_WRITE", OSError(errno.EIO, "sync error")),
        ("BEFORE_JOURNAL_RENAME", PermissionError(errno.EACCES, "denied")),
    ],
)
def test_journal_writer_faults_are_durable_errors(
    tmp_path: Path, point: str, error: OSError
) -> None:
    path = tmp_path / "journal.json"
    JournalStore(path).save(_record())

    def inject(current: str, target: Path) -> None:
        if current == point:
            if point == "DURING_JOURNAL_WRITE":
                target.write_text("{truncated", encoding="utf-8")
            raise type(error)(error.errno, str(error))

    store = JournalStore(path, fault_injector=inject)
    record = JournalStore(path).load()
    assert record is not None
    with pytest.raises(JournalDurabilityError):
        store.save(record.advance(state="LOCKED"))

    if point == "DURING_JOURNAL_WRITE":
        with pytest.raises(JournalCorruptError):
            JournalStore(path).load()
    else:
        assert JournalStore(path).load() is not None


@pytest.mark.parametrize("point", ["BEFORE_SNAPSHOT_WRITE", "DURING_SNAPSHOT_WRITE", "BEFORE_SNAPSHOT_RENAME"])
def test_snapshot_writer_faults_never_report_success(tmp_path: Path, point: str) -> None:
    path = tmp_path / "snapshot.json"

    def inject(current: str, target: Path) -> None:
        if current == point:
            if point == "DURING_SNAPSHOT_WRITE":
                target.write_text("{truncated", encoding="utf-8")
            raise OSError(errno.EIO, "injected snapshot failure")

    with pytest.raises(Exception, match="Snapshot"):
        SnapshotStore(path, fault_injector=inject).save(_snapshot(tmp_path))
    if point == "DURING_SNAPSHOT_WRITE":
        with pytest.raises(SnapshotCorruptError):
            SnapshotStore(path).load()


def test_journal_symlink_and_hardlink_are_not_trusted(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text(json.dumps(_record().as_dict()), encoding="utf-8")
    symlink = tmp_path / "symlink.json"
    symlink.symlink_to(target)
    with pytest.raises(JournalCorruptError, match="Symlink"):
        JournalStore(symlink).load()

    hardlink = tmp_path / "hardlink.json"
    hardlink.hardlink_to(target)
    with pytest.raises(JournalCorruptError, match="Hardlink"):
        JournalStore(hardlink).load()
