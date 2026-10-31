"""Fail-closed transactional scaffolding for isolated native migration tests.

The engine is deliberately not wired to a Home Assistant WebSocket or Apply
endpoint.  Its execution method requires an explicit isolated-test permit.
Production code can use the preflight and recovery data types, but cannot
invoke native source mutation through this module by accident.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace

from .migration_journal import JournalRecord, JournalStore
from .migration_lock import BridgeMigrationLock
from .migration_recovery import RecoveryDecision, classify
from .migration_snapshot import MigrationSnapshot, SnapshotStore


class MigrationEngineError(Exception):
    """Base class for migration-engine failures."""


class MigrationDisabled(MigrationEngineError):
    """Native execution is not enabled for production code."""


class InvalidTransition(MigrationEngineError):
    """A state transition violates the transaction graph."""


class BaselineChanged(MigrationEngineError):
    """The expected revision changed before a critical step."""


STATES = (
    "IDLE",
    "PREFLIGHT",
    "LOCKED",
    "SNAPSHOT_CREATED",
    "PREPARED",
    "QUIESCING",
    "SOURCE_SWITCHING",
    "RELOADING",
    "VERIFYING",
    "COMMITTED",
    "ROLLBACK_REQUIRED",
    "ROLLING_BACK",
    "ROLLED_BACK",
    "FAILED",
    "MANUAL_RECOVERY_REQUIRED",
)

TRANSITIONS = {
    "PREFLIGHT": {"LOCKED", "FAILED"},
    "LOCKED": {"SNAPSHOT_CREATED", "FAILED"},
    "SNAPSHOT_CREATED": {"PREPARED", "FAILED"},
    "PREPARED": {"QUIESCING", "FAILED"},
    "QUIESCING": {"SOURCE_SWITCHING", "ROLLBACK_REQUIRED", "FAILED"},
    "SOURCE_SWITCHING": {"RELOADING", "ROLLBACK_REQUIRED", "FAILED"},
    "RELOADING": {"VERIFYING", "ROLLBACK_REQUIRED", "FAILED"},
    "VERIFYING": {"COMMITTED", "ROLLBACK_REQUIRED", "FAILED"},
    "ROLLBACK_REQUIRED": {"ROLLING_BACK", "MANUAL_RECOVERY_REQUIRED"},
    "ROLLING_BACK": {"ROLLED_BACK", "MANUAL_RECOVERY_REQUIRED"},
}


Step = Callable[[], Mapping[str, str] | None]
AsyncStep = Callable[[], Awaitable[Mapping[str, str] | None]]


@dataclass(frozen=True)
class MigrationPlan:
    bridge_id: str
    source: str
    target: str
    baseline_fingerprint: str
    config_revision: str


@dataclass(frozen=True)
class MigrationResult:
    transaction_id: str
    state: str
    record: JournalRecord


class MigrationEngine:
    """Persist state before each side effect and fail closed on ambiguity."""

    def __init__(
        self,
        *,
        journal: JournalStore,
        snapshots: SnapshotStore,
        lock: BridgeMigrationLock,
        experimental_test_permit: bool = False,
    ):
        self.journal = journal
        self.snapshots = snapshots
        self.lock = lock
        self.experimental_test_permit = experimental_test_permit

    def preflight(self, plan: MigrationPlan) -> JournalRecord:
        """Create the first durable record without touching native state."""
        if not plan.bridge_id or plan.source == plan.target:
            raise MigrationEngineError("Bridge und Quellenwechsel müssen eindeutig sein")
        if plan.source not in {"user", "import"} or plan.target not in {"user", "import"}:
            raise MigrationEngineError("Nur bekannte HomeKit-Quellen sind zulässig")
        if not plan.baseline_fingerprint or not plan.config_revision:
            raise MigrationEngineError("Baseline und Revision sind Pflicht")
        current = self.journal.load()
        if current and classify(current).action != "none":
            raise MigrationEngineError("Eine unvollständige Transaktion blockiert den Start")
        record = JournalRecord.new(
            bridge_id=plan.bridge_id,
            source=plan.source,
            target=plan.target,
            baseline_fingerprint=plan.baseline_fingerprint,
            config_revision=plan.config_revision,
        )
        return self.journal.save(record)

    def recover_status(self) -> RecoveryDecision:
        """Return a decision only; never mutate Core or HAP state."""
        return classify(self.journal.load())

    def rollback(self, rollback_step: Step) -> MigrationResult:
        """Run an explicitly requested rollback, never an automatic recovery."""
        if not self.experimental_test_permit:
            raise MigrationDisabled("Native Quellenmigration ist außerhalb isolierter Tests deaktiviert")
        record = self.journal.load()
        if record is None or record.state != "ROLLBACK_REQUIRED":
            raise MigrationEngineError("Kein eindeutig rollbackfähiger Zustand vorhanden")
        try:
            self.lock.acquire()
            record = self._step(record, "ROLLING_BACK", "rollback", rollback_step)
            record = self._step(record, "ROLLED_BACK", "rollback_complete", None)
            return MigrationResult(record.transaction_id, record.state, record)
        except Exception as err:
            record = self.journal.load() or record
            self._persist(record, "MANUAL_RECOVERY_REQUIRED", error=str(err), recovery_status="rollback_failed")
            raise
        finally:
            self.lock.release()

    async def rollback_async(self, rollback_step: AsyncStep) -> MigrationResult:
        """Run an explicitly requested asynchronous rollback.

        Recovery remains an explicit administrative decision.  This method is
        provided for a future Home Assistant lifecycle integration, but the
        production migration endpoint remains disabled.
        """
        if not self.experimental_test_permit:
            raise MigrationDisabled("Native Quellenmigration ist außerhalb isolierter Tests deaktiviert")
        record = self.journal.load()
        if record is None or record.state != "ROLLBACK_REQUIRED":
            raise MigrationEngineError("Kein eindeutig rollbackfähiger Zustand vorhanden")
        try:
            self.lock.acquire()
            record = await self._step_async(record, "ROLLING_BACK", "rollback", rollback_step)
            record = self._persist(record, "ROLLED_BACK", operation="rollback_complete")
            return MigrationResult(record.transaction_id, record.state, record)
        except Exception as err:
            record = self.journal.load() or record
            self._persist(record, "MANUAL_RECOVERY_REQUIRED", error=str(err), recovery_status="rollback_failed")
            raise
        finally:
            self.lock.release()

    async def execute_async(
        self,
        plan: MigrationPlan,
        *,
        steps: Mapping[str, AsyncStep],
        snapshot: MigrationSnapshot,
        expected_revision: Callable[[], str] | None = None,
        auto_rollback: bool = False,
    ) -> MigrationResult:
        """Async equivalent for Home Assistant lifecycle callbacks.

        This remains behind the same isolated-test permit.  The durable state
        boundaries intentionally mirror :meth:`execute`.
        """
        if not self.experimental_test_permit:
            raise MigrationDisabled("Native Quellenmigration ist außerhalb isolierter Tests deaktiviert")
        record = self.preflight(plan)
        snapshot = replace(snapshot, transaction_id=record.transaction_id)
        self.snapshots.save(snapshot)
        try:
            self.lock.acquire()
            record = await self._step_async(record, "LOCKED", "lock", steps.get("lock"))
            record = await self._step_async(
                record,
                "SNAPSHOT_CREATED",
                "snapshot",
                steps.get("snapshot"),
                checksums={"snapshot": snapshot.fingerprint},
            )
            record = await self._step_async(record, "PREPARED", "prepare", steps.get("prepare"))
            record = await self._step_async(record, "QUIESCING", "quiesce", steps.get("quiesce"))
            self._check_revision(expected_revision, plan.config_revision)
            record = await self._step_async(record, "SOURCE_SWITCHING", "source_switch", steps.get("source_switch"))
            self._check_revision(expected_revision, plan.config_revision)
            record = await self._step_async(record, "RELOADING", "reload", steps.get("reload"))
            self._check_revision(expected_revision, plan.config_revision)
            record = await self._step_async(record, "VERIFYING", "verify", steps.get("verify"))
            record = await self._step_async(record, "COMMITTED", "commit", steps.get("commit"))
            return MigrationResult(record.transaction_id, record.state, record)
        except Exception as err:
            record = self.journal.load() or record
            if record.state in {"PREFLIGHT", "LOCKED", "SNAPSHOT_CREATED", "PREPARED"}:
                self._persist(record, "FAILED", error=str(err), recovery_status="failed_before_native_change")
            else:
                record = self._persist(record, "ROLLBACK_REQUIRED", error=str(err), recovery_status="rollback_required")
                if auto_rollback and "rollback" in steps:
                    try:
                        record = await self._step_async(record, "ROLLING_BACK", "rollback", steps["rollback"])
                        self._persist(record, "ROLLED_BACK", operation="rollback_complete")
                    except Exception as rollback_err:
                        self._persist(
                            self.journal.load() or record,
                            "MANUAL_RECOVERY_REQUIRED",
                            error=f"{err}; Rollback fehlgeschlagen: {rollback_err}",
                            recovery_status="rollback_failed",
                        )
                        raise
            raise
        finally:
            self.lock.release()

    def execute(
        self,
        plan: MigrationPlan,
        *,
        steps: Mapping[str, Step],
        snapshot: MigrationSnapshot,
        expected_revision: Callable[[], str] | None = None,
        auto_rollback: bool = False,
    ) -> MigrationResult:
        """Execute only under an explicit isolated-test permit.

        Each step first persists its state, then performs the callback, then
        persists the completed operation.  A process kill between those writes
        therefore remains visibly ambiguous and is classified conservatively.
        """
        if not self.experimental_test_permit:
            raise MigrationDisabled("Native Quellenmigration ist außerhalb isolierter Tests deaktiviert")
        record = self.preflight(plan)
        snapshot = replace(snapshot, transaction_id=record.transaction_id)
        self.snapshots.save(snapshot)
        try:
            self.lock.acquire()
            record = self._step(record, "LOCKED", "lock", steps.get("lock"))
            record = self._step(
                record,
                "SNAPSHOT_CREATED",
                "snapshot",
                steps.get("snapshot"),
                checksums={"snapshot": snapshot.fingerprint},
            )
            record = self._step(record, "PREPARED", "prepare", steps.get("prepare"))
            record = self._step(record, "QUIESCING", "quiesce", steps.get("quiesce"))
            self._check_revision(expected_revision, plan.config_revision)
            record = self._step(record, "SOURCE_SWITCHING", "source_switch", steps.get("source_switch"))
            self._check_revision(expected_revision, plan.config_revision)
            record = self._step(record, "RELOADING", "reload", steps.get("reload"))
            self._check_revision(expected_revision, plan.config_revision)
            record = self._step(record, "VERIFYING", "verify", steps.get("verify"))
            record = self._step(record, "COMMITTED", "commit", steps.get("commit"))
            return MigrationResult(record.transaction_id, record.state, record)
        except Exception as err:
            record = self.journal.load() or record
            if record.state in {"PREFLIGHT", "LOCKED", "SNAPSHOT_CREATED", "PREPARED"}:
                record = self._persist(record, "FAILED", error=str(err), recovery_status="failed_before_native_change")
            else:
                record = self._persist(record, "ROLLBACK_REQUIRED", error=str(err), recovery_status="rollback_required")
                if auto_rollback and "rollback" in steps:
                    try:
                        record = self._step(record, "ROLLING_BACK", "rollback", steps["rollback"])
                        record = self._step(record, "ROLLED_BACK", "rollback_complete", None)
                    except Exception as rollback_err:
                        self._persist(
                            self.journal.load() or record,
                            "MANUAL_RECOVERY_REQUIRED",
                            error=f"{err}; Rollback fehlgeschlagen: {rollback_err}",
                            recovery_status="rollback_failed",
                        )
                        raise
            raise
        finally:
            self.lock.release()

    @staticmethod
    def _check_revision(expected_revision: Callable[[], str] | None, baseline: str) -> None:
        if expected_revision and expected_revision() != baseline:
            raise BaselineChanged("Die Konfigurationsrevision hat sich während der Migration geändert")

    def _step(
        self,
        record: JournalRecord,
        state: str,
        operation: str,
        callback: Step | None,
        *,
        checksums: Mapping[str, str] | None = None,
    ) -> JournalRecord:
        if state not in TRANSITIONS.get(record.state, set()):
            raise InvalidTransition(f"{record.state} -> {state} ist nicht zulässig")
        record = self._persist(record, state, checksums=checksums)
        if callback:
            result = callback()
            result_checksums = dict(checksums or {})
            if result:
                result_checksums.update(result)
        else:
            result_checksums = dict(checksums or {})
        return self._persist(record, state, operation=operation, checksums=result_checksums)

    async def _step_async(
        self,
        record: JournalRecord,
        state: str,
        operation: str,
        callback: AsyncStep | None,
        *,
        checksums: Mapping[str, str] | None = None,
    ) -> JournalRecord:
        if state not in TRANSITIONS.get(record.state, set()):
            raise InvalidTransition(f"{record.state} -> {state} ist nicht zulässig")
        record = self._persist(record, state, checksums=checksums)
        result = await callback() if callback else None
        result_checksums = dict(checksums or {})
        if result:
            result_checksums.update(result)
        return self._persist(record, state, operation=operation, checksums=result_checksums)

    def _persist(
        self,
        record: JournalRecord,
        state: str,
        *,
        operation: str | None = None,
        checksums: Mapping[str, str] | None = None,
        error: str | None = None,
        recovery_status: str | None = None,
    ) -> JournalRecord:
        updated = record.advance(
            state=state,
            completed_operation=operation,
            checksums=checksums,
            error=error,
            recovery_status=recovery_status,
        )
        return self.journal.save(updated)
