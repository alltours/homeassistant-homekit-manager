"""State-machine, durability and rollback tests for the isolated engine."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from custom_components.homekit_manager.migration_engine import (
    MigrationDisabled,
    MigrationEngine,
    MigrationEngineError,
    MigrationPlan,
)
from custom_components.homekit_manager.migration_journal import (
    JournalCorruptError,
    JournalError,
    JournalRecord,
    JournalStore,
)
from custom_components.homekit_manager.migration_lock import (
    BridgeMigrationLock,
    MigrationLockBusy,
)
from custom_components.homekit_manager.migration_recovery import classify, inspect_store
from custom_components.homekit_manager.migration_snapshot import (
    MigrationSnapshot,
    SnapshotStore,
)


def _plan() -> MigrationPlan:
    return MigrationPlan(
        bridge_id="bridge-a",
        source="user",
        target="import",
        baseline_fingerprint="baseline-1",
        config_revision="revision-1",
    )


def _engine(tmp_path: Path, *, permit: bool = True) -> MigrationEngine:
    return MigrationEngine(
        journal=JournalStore(tmp_path / "journal.json"),
        snapshots=SnapshotStore(tmp_path / "snapshot.json"),
        lock=BridgeMigrationLock(tmp_path / "bridge.lock", "bridge-a"),
        experimental_test_permit=permit,
    )


def _snapshot(tmp_path: Path) -> MigrationSnapshot:
    source = tmp_path / "configuration.yaml"
    source.write_text("homekit: []\n", encoding="utf-8")
    return MigrationSnapshot.build(
        transaction_id="pending",
        bridge_id="bridge-a",
        logical={"entry_id": "bridge-a", "pairing_secret": "must-not-persist"},
        files={"configuration.yaml": source},
        secret_fingerprints={"pairing": b"secret"},
    )


def test_snapshot_is_redacted_and_deterministic(tmp_path):
    snapshot = _snapshot(tmp_path)
    encoded = str(snapshot.as_dict())
    assert "must-not-persist" not in encoded
    assert snapshot.logical["pairing_secret"] == "<" + "redacted>"
    assert snapshot.secret_fingerprints["pairing"] != "secret"
    assert snapshot.fingerprint == MigrationSnapshot.build(
        transaction_id="other",
        bridge_id="bridge-a",
        logical={"entry_id": "bridge-a", "pairing_secret": "must-not-persist"},
        files={"configuration.yaml": tmp_path / "configuration.yaml"},
        secret_fingerprints={"pairing": b"secret"},
    ).fingerprint


def test_journal_round_trip_is_durable_and_validated(tmp_path):
    path = tmp_path / "journal.json"
    store = JournalStore(path)
    record = JournalRecord.new(
        bridge_id="bridge-a",
        source="user",
        target="import",
        baseline_fingerprint="baseline-1",
        config_revision="revision-1",
    )
    store.save(record)
    with pytest.raises(JournalError):
        store.save(record)
    loaded = store.load()
    assert loaded == record
    assert path.stat().st_mode & 0o777 == 0o600
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(JournalCorruptError):
        store.load()
    assert inspect_store(store).action == "manual_recovery"


def test_engine_requires_explicit_isolated_permit(tmp_path):
    engine = _engine(tmp_path, permit=False)
    with pytest.raises(MigrationDisabled):
        engine.execute(_plan(), steps={}, snapshot=_snapshot(tmp_path))
    assert not (tmp_path / "journal.json").exists()


def test_engine_persists_every_state_and_commits(tmp_path):
    engine = _engine(tmp_path)
    executed: list[str] = []

    def step(name):
        def callback():
            executed.append(name)
            return {name: f"checksum-{name}"}

        return callback

    steps = {name: step(name) for name in (
        "lock", "snapshot", "prepare", "quiesce", "source_switch", "reload", "verify", "commit"
    )}
    result = engine.execute(
        _plan(),
        steps=steps,
        snapshot=_snapshot(tmp_path),
        expected_revision=lambda: "revision-1",
    )
    assert result.state == "COMMITTED"
    assert executed == list(steps)
    assert set(result.record.completed_operations) == set(steps)
    assert engine.recover_status().action == "none"


def test_engine_fault_points_are_opt_in_and_ordered(tmp_path):
    points: list[str] = []
    engine = MigrationEngine(
        journal=JournalStore(tmp_path / "journal.json"),
        snapshots=SnapshotStore(tmp_path / "snapshot.json"),
        lock=BridgeMigrationLock(tmp_path / "bridge.lock", "bridge-a"),
        experimental_test_permit=True,
        fault_injector=points.append,
    )
    engine.execute(
        _plan(),
        steps={name: (lambda: None) for name in (
            "lock", "snapshot", "prepare", "quiesce", "source_switch", "reload", "verify", "commit"
        )},
        snapshot=_snapshot(tmp_path),
    )
    assert "BEFORE_PREFLIGHT" in points
    assert "AFTER_PREFLIGHT" in points
    assert "AFTER_SNAPSHOT" in points
    assert "BEFORE_SOURCE_MUTATION" in points
    assert "AFTER_COMMIT" in points


def test_async_engine_uses_the_same_durable_boundaries(tmp_path):
    engine = _engine(tmp_path)
    executed: list[str] = []

    async def step(name):
        await asyncio.sleep(0)
        executed.append(name)
        return {name: f"async-{name}"}

    steps = {name: (lambda name=name: step(name)) for name in (
        "lock", "snapshot", "prepare", "quiesce", "source_switch", "reload", "verify", "commit"
    )}
    result = asyncio.run(
        engine.execute_async(
            _plan(), steps=steps, snapshot=_snapshot(tmp_path),
            expected_revision=lambda: "revision-1",
        )
    )
    assert result.state == "COMMITTED"
    assert executed == list(steps)


def test_revision_change_blocks_before_source_switch(tmp_path):
    engine = _engine(tmp_path)
    with pytest.raises(MigrationEngineError, match="Revision|revision"):
        engine.execute(
            _plan(),
            steps={"quiesce": lambda: None, "source_switch": lambda: None},
            snapshot=_snapshot(tmp_path),
            expected_revision=lambda: "revision-2",
        )
    record = JournalStore(tmp_path / "journal.json").load()
    assert record is not None
    assert record.state == "ROLLBACK_REQUIRED"


def test_explicit_rollback_restores_test_state(tmp_path):
    engine = _engine(tmp_path)
    native_state = {"source": "user"}

    def switch():
        native_state["source"] = "import"
        raise RuntimeError("injected source failure")

    with pytest.raises(RuntimeError):
        engine.execute(
            _plan(),
            steps={"source_switch": switch},
            snapshot=_snapshot(tmp_path),
        )
    assert engine.recover_status().action == "manual_recovery"

    result = engine.rollback(lambda: native_state.update(source="user"))
    assert result.state == "ROLLED_BACK"
    assert native_state["source"] == "user"


def test_async_explicit_rollback_restores_test_state(tmp_path):
    engine = _engine(tmp_path)
    native_state = {"source": "user"}

    async def switch():
        native_state["source"] = "import"
        raise RuntimeError("source failed")

    with pytest.raises(RuntimeError):
        asyncio.run(
            engine.execute_async(
                _plan(),
                steps={"source_switch": lambda: switch()},
                snapshot=_snapshot(tmp_path),
            )
        )

    async def rollback():
        native_state["source"] = "user"

    result = asyncio.run(engine.rollback_async(rollback))
    assert result.state == "ROLLED_BACK"
    assert native_state["source"] == "user"


def test_failed_automatic_rollback_requires_manual_recovery(tmp_path):
    engine = _engine(tmp_path)

    def source_failure():
        raise RuntimeError("source failed")

    def rollback_failure():
        raise RuntimeError("rollback failed")

    with pytest.raises(RuntimeError, match="rollback failed"):
        engine.execute(
            _plan(),
            steps={"source_switch": source_failure, "rollback": rollback_failure},
            snapshot=_snapshot(tmp_path),
            auto_rollback=True,
        )
    record = JournalStore(tmp_path / "journal.json").load()
    assert record is not None
    assert record.state == "MANUAL_RECOVERY_REQUIRED"


def test_recovery_never_auto_commits_ambiguous_states(tmp_path):
    store = JournalStore(tmp_path / "journal.json")
    record = JournalRecord.new(
        bridge_id="bridge-a", source="user", target="import",
        baseline_fingerprint="baseline-1", config_revision="revision-1",
    )
    store.save(record.advance(state="SOURCE_SWITCHING"))
    decision = classify(store.load())
    assert decision.action == "manual_recovery"
    assert decision.automatic is False
    assert decision.outcome == "MANUAL_RECOVERY_REQUIRED"


def test_lock_rejects_second_process_handle(tmp_path):
    first = BridgeMigrationLock(tmp_path / "bridge.lock", "bridge-a")
    second = BridgeMigrationLock(tmp_path / "bridge.lock", "bridge-a")
    first.acquire()
    try:
        with pytest.raises(MigrationLockBusy):
            second.acquire()
    finally:
        first.release()
