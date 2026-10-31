"""Read-only startup recovery boundary for native HomeKit migrations.

Home Assistant does not provide a lifecycle hook that runs before the native
HomeKit YAML importer.  A custom integration must therefore never mutate a
HomeKit entry from its normal setup callback merely because it finds an
unfinished journal.  This module deliberately observes and classifies the
journal only.  An incomplete or corrupt record is reported as requiring
manual recovery and cannot authorize a source mutation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .migration_journal import JournalStore
from .migration_recovery import (
    MANUAL_RECOVERY_REQUIRED,
    inspect_store,
)

STARTUP_RECOVERY_SCHEMA = 1
STARTUP_RECOVERY_BLOCKED_REASON = (
    "Home Assistant garantiert für Custom Integrations keinen Vorlauf vor "
    "der nativen HomeKit-YAML-Reconciliation; automatische Quellenmutation "
    "ist deshalb gesperrt."
)


@dataclass(frozen=True)
class StartupRecoveryObservation:
    """A redacted, non-mutating startup observation."""

    state: str
    action: str
    automatic: bool
    native_mutation_allowed: bool
    reason: str
    transaction_id: str | None = None
    source: str | None = None
    target: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a frontend-safe representation without secrets."""
        return {
            "schema": STARTUP_RECOVERY_SCHEMA,
            "state": self.state,
            "action": self.action,
            "automatic": self.automatic,
            "native_mutation_allowed": self.native_mutation_allowed,
            "reason": self.reason,
            "transaction_id": self.transaction_id,
            "source": self.source,
            "target": self.target,
        }


def default_journal_path(hass: Any) -> Path:
    """Return the reserved journal path used only by future isolated engines."""
    return Path(hass.config.path(".storage", "homekit_manager.native_migration.journal.json"))


def observe_startup_recovery(journal_path: str | Path) -> StartupRecoveryObservation:
    """Inspect a journal without writing files or changing Home Assistant.

    The reserved journal must be a regular file.  Symlinks and unreadable
    filesystem states are ambiguous and therefore fail closed.
    """
    path = Path(journal_path)
    try:
        if path.is_symlink():
            return StartupRecoveryObservation(
                "UNKNOWN",
                "manual_recovery",
                False,
                False,
                "Der Recovery-Journalpfad ist ein Symlink; automatische Recovery ist gesperrt.",
            )
        if not path.exists():
            return StartupRecoveryObservation(
                "IDLE",
                "none",
                False,
                False,
                "Kein unvollständiges natives Migrationsjournal vorhanden.",
            )
        if not path.is_file():
            return StartupRecoveryObservation(
                "UNKNOWN",
                "manual_recovery",
                False,
                False,
                "Der Recovery-Journalpfad ist keine reguläre Datei; automatische Recovery ist gesperrt.",
            )
        decision = inspect_store(JournalStore(path))
    except OSError as err:
        return StartupRecoveryObservation(
            "UNKNOWN",
            "manual_recovery",
            False,
            False,
            f"Recovery-Journal konnte nicht sicher gelesen werden: {type(err).__name__}",
        )

    if decision.outcome == MANUAL_RECOVERY_REQUIRED or decision.action != "none":
        return StartupRecoveryObservation(
            decision.state,
            "manual_recovery",
            False,
            False,
            STARTUP_RECOVERY_BLOCKED_REASON + " " + decision.reason,
            decision.transaction_id,
        )

    # A terminal record is evidence only.  It never authorizes a new mutation.
    return StartupRecoveryObservation(
        decision.state,
        "none",
        False,
        False,
        decision.reason,
        decision.transaction_id,
    )
