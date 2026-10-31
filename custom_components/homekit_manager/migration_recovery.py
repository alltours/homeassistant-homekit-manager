"""Conservative recovery decisions for incomplete migration journals."""
from __future__ import annotations

from dataclasses import dataclass

from .migration_journal import JournalCorruptError, JournalRecord, JournalStore, TERMINAL_STATES


@dataclass(frozen=True)
class RecoveryDecision:
    """A decision without performing any Home Assistant mutation."""

    transaction_id: str | None
    state: str
    action: str
    reason: str
    automatic: bool


def classify(record: JournalRecord | None) -> RecoveryDecision:
    """Classify a journal conservatively after process loss."""
    if record is None:
        return RecoveryDecision(None, "IDLE", "none", "Kein aktiver Migrationsdatensatz", False)
    if record.state in TERMINAL_STATES and (
        record.state != "COMMITTED" or "commit" in record.completed_operations
    ) and (
        record.state != "ROLLED_BACK" or "rollback_complete" in record.completed_operations
    ):
        return RecoveryDecision(record.transaction_id, record.state, "none", "Transaktion ist abgeschlossen", False)
    if record.state in {"PREFLIGHT", "LOCKED", "SNAPSHOT_CREATED", "PREPARED"}:
        return RecoveryDecision(
            record.transaction_id,
            record.state,
            "resume_preflight",
            "Es wurde noch keine irreversible Quellenänderung bestätigt",
            False,
        )
    if record.state == "QUIESCING" and "quiesce" not in record.completed_operations:
        return RecoveryDecision(
            record.transaction_id,
            record.state,
            "manual_recovery",
            "Der Runtime-Zustand nach dem Abbruch des Quiesce-Schritts ist unbekannt",
            False,
        )
    return RecoveryDecision(
        record.transaction_id,
        record.state,
        "manual_recovery",
        "Nach dem Quiesce-Schritt kann der native Zustand nicht ohne externe Verifikation automatisch beurteilt werden",
        False,
    )


def inspect_store(store: JournalStore) -> RecoveryDecision:
    """Read and classify a journal; corruption always blocks automation."""
    try:
        return classify(store.load())
    except JournalCorruptError as err:
        return RecoveryDecision(None, "UNKNOWN", "manual_recovery", str(err), False)
