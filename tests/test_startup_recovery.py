"""Unit tests for the fail-closed startup recovery boundary."""
from __future__ import annotations

import json

from custom_components.homekit_manager.migration_journal import (
    JournalRecord,
    JournalStore,
)
from custom_components.homekit_manager.startup_recovery import observe_startup_recovery


def _record(path, *, state: str = "SOURCE_SWITCHING") -> None:
    record = JournalRecord.new(
        bridge_id="entry-a",
        source="import",
        target="user",
        baseline_fingerprint="baseline",
        config_revision="revision",
    ).advance(state=state)
    JournalStore(path).save(record)


def test_missing_journal_is_read_only_idle(tmp_path):
    path = tmp_path / "journal.json"
    result = observe_startup_recovery(path)
    assert result.state == "IDLE"
    assert result.native_mutation_allowed is False
    assert not path.exists()


def test_incomplete_journal_is_blocked_without_mutation(tmp_path):
    path = tmp_path / "journal.json"
    _record(path)
    before = path.read_bytes()

    result = observe_startup_recovery(path)

    assert result.action == "manual_recovery"
    assert result.automatic is False
    assert result.native_mutation_allowed is False
    assert result.transaction_id
    assert path.read_bytes() == before


def test_corrupt_journal_is_blocked(tmp_path):
    path = tmp_path / "journal.json"
    path.write_text("{not-json", encoding="utf-8")

    result = observe_startup_recovery(path)

    assert result.state == "UNKNOWN"
    assert result.action == "manual_recovery"
    assert result.native_mutation_allowed is False


def test_terminal_journal_is_evidence_only(tmp_path):
    path = tmp_path / "journal.json"
    record = JournalRecord.new(
        bridge_id="entry-a",
        source="user",
        target="import",
        baseline_fingerprint="baseline",
        config_revision="revision",
    ).advance(state="COMMITTED", completed_operation="commit")
    JournalStore(path).save(record)
    before = json.loads(path.read_text(encoding="utf-8"))

    result = observe_startup_recovery(path)

    assert result.state == "COMMITTED"
    assert result.action == "none"
    assert result.native_mutation_allowed is False
    assert json.loads(path.read_text(encoding="utf-8")) == before
