"""Full-Core crash tests for the Core-owned transaction protocol v2."""
from __future__ import annotations

from tempfile import TemporaryDirectory

import pytest
from test_core_multibridge_migration_015 import _run


@pytest.mark.parametrize("direction", ["ui_to_yaml", "yaml_to_ui"])
@pytest.mark.parametrize(
    "fault", ["AFTER_PREPARE_DURABLE", "AFTER_SOURCE_SWITCH_PENDING", "AFTER_SOURCE_SWITCH_DURABLE"]
)
def test_protocol_v2_wal_boundaries_recover_or_block_safely(
    direction: str, fault: str
) -> None:
    """Every durable boundary ends in a verified target or safe block."""
    with TemporaryDirectory(prefix=f"hkm-core-protocol-017-{direction}-{fault}-") as directory:
        assert _run(directory, direction, "pair").returncode == 0
        crashed = _run(directory, direction, "migrate", fault=fault)
        assert crashed.returncode == -9, crashed.stdout + crashed.stderr

        if fault == "AFTER_SOURCE_SWITCH_DURABLE":
            expected_source = "import" if direction == "ui_to_yaml" else "user"
        else:
            expected_source = "user" if direction == "ui_to_yaml" else "import"
        recovered = _run(directory, direction, "verify", expected_source=expected_source)
        assert recovered.returncode == 0, recovered.stdout + recovered.stderr


@pytest.mark.parametrize("direction", ["ui_to_yaml", "yaml_to_ui"])
def test_protocol_v2_commit_pending_is_idempotent_after_second_crash(direction: str) -> None:
    """A crash after COMMIT_PENDING is completed by the next startup."""
    with TemporaryDirectory(prefix=f"hkm-core-protocol-017-commit-{direction}-") as directory:
        assert _run(directory, direction, "pair").returncode == 0
        assert _run(directory, direction, "migrate").returncode == -9

        first_recovery = _run(directory, direction, "verify", fault="AFTER_COMMIT_PENDING")
        assert first_recovery.returncode == -9, first_recovery.stdout + first_recovery.stderr

        second_recovery = _run(directory, direction, "verify")
        assert second_recovery.returncode == 0, second_recovery.stdout + second_recovery.stderr

