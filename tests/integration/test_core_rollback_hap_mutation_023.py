"""Adversarial full-Core HAP mutations during Core-owned rollback.

These tests deliberately mutate isolated Bridge A persistence after a real
SIGKILL during rollback.  They must prove that the Core refuses to publish the
damaged bridge and never treats the rollback as successful.  Bridge B is the
independent liveness control.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from test_core_hap_mutation_security_022 import _mutate
from test_core_multibridge_migration_015 import _run

pytestmark = pytest.mark.experimental_core


def _write_json(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.rollback-mutation")
    temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _mutate_transaction(root: Path, mutation: str) -> None:
    """Corrupt only the isolated transaction envelope for Bridge A."""
    path = root / ".storage" / "homekit.migration"
    envelope = json.loads(path.read_text(encoding="utf-8"))
    data = envelope["data"]
    if mutation == "journal":
        data["entry_id"] = "not-bridge-a"
    elif mutation == "snapshot":
        # The Core protocol stores the durable baseline fingerprint in its
        # transaction snapshot.  A mismatch must be rejected by normalization.
        data["baseline_fingerprint"] = "0" * 64
        data["baseline_revision"] = "0" * 64
    else:
        raise AssertionError(f"Unknown transaction mutation: {mutation}")
    _write_json(path, envelope)


@pytest.mark.parametrize("direction", ["ui_to_yaml", "yaml_to_ui"])
@pytest.mark.parametrize(
    "mutation",
    [
        "mac",
        "pairing",
        "aid_iid",
        "allowlist",
        "duplicate",
        "journal",
        "snapshot",
    ],
)
def test_rollback_hap_mutation_is_fail_closed_and_scoped(
    direction: str, mutation: str
) -> None:
    """A damaged rollback cannot publish A or impair unrelated Bridge B."""
    with TemporaryDirectory(
        prefix=f"hkm-core-rollback-mutation-023-{direction}-{mutation}-"
    ) as directory:
        root = Path(directory)
        paired = _run(directory, direction, "pair")
        assert paired.returncode == 0, paired.stdout + paired.stderr

        crashed = _run(
            directory,
            direction,
            "rollback",
            fault="AFTER_ROLLBACK_SOURCE_MUTATION",
        )
        assert crashed.returncode == -9, crashed.stdout + crashed.stderr
        assert (root / "fault-reached").read_text(encoding="utf-8") == (
            "AFTER_ROLLBACK_SOURCE_MUTATION"
        )

        if mutation in {"mac", "pairing", "aid_iid", "allowlist", "duplicate"}:
            _mutate(root, mutation)
        else:
            _mutate_transaction(root, mutation)

        observed = _run(directory, direction, "security_verify")
        assert observed.returncode == 0, observed.stdout + observed.stderr
        evidence = json.loads(
            (root / "security-observation.json").read_text(encoding="utf-8")
        )

        journal = evidence["journal"]
        if mutation in {"journal", "snapshot"}:
            # The Core must not overwrite untrusted evidence merely to make
            # the record look terminal.  The startup observation is the
            # authoritative safety decision for a malformed request.
            assert journal["state"] == "ROLLING_BACK", evidence
            assert evidence["migration"]["state"] == "MANUAL_RECOVERY_REQUIRED", evidence
        else:
            assert journal["state"] == "MANUAL_RECOVERY_REQUIRED", evidence
            assert journal["commit_status"] == "MANUAL_RECOVERY_REQUIRED", evidence
        assert evidence["reconnect"]["Bridge A"]["ok"] is False, evidence

        # A valid, bridge-scoped identity failure must not take B down.  A
        # malformed transaction envelope has no trustworthy identity and is
        # intentionally allowed to block all native HomeKit publication.
        if mutation in {"journal", "snapshot"}:
            assert evidence["reconnect"]["Bridge B"]["ok"] is False, evidence
        else:
            assert evidence["reconnect"]["Bridge B"]["ok"] is True, evidence

        expected_entries = 3 if mutation == "duplicate" else 2
        assert evidence["entry_count"] == expected_entries, evidence
        assert evidence["active_bridge_count"] <= 1, evidence
