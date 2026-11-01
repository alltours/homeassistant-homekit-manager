"""Full-Core HAP persistence mutation security controls for 0.10.22."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

pytestmark = pytest.mark.experimental_core

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "tests/integration/_core_multibridge_migration_worker_015.py"
ENTRY_A = "isolated-multi-bridge-a-015"


def _run(directory: str, direction: str, phase: str) -> subprocess.CompletedProcess[str]:
    environment = dict(
        os.environ,
        HKM_CORE_MULTIBRIDGE_DIR=directory,
        HKM_CORE_MULTIBRIDGE_DIRECTION=direction,
        HKM_CORE_MULTIBRIDGE_PHASE=phase,
        PYTHONPATH=os.pathsep.join(
            item for item in (str(ROOT), os.environ.get("PYTHONPATH", "")) if item
        ),
    )
    return subprocess.run(
        [sys.executable, "-X", "faulthandler", str(WORKER)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )


def _write_json(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.mutation")
    temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def _entry_id(directory: Path) -> str:
    baseline = json.loads((directory / "bridge_a.baseline.json").read_text(encoding="utf-8"))
    return baseline["logical"]["entry_id"]


def _mutate(directory: Path, mutation: str) -> None:
    entry_id = _entry_id(directory)
    state_path = directory / ".storage" / f"homekit.{entry_id}.state"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if mutation == "mac":
        state["mac"] = "02:00:00:00:22:01"
        _write_json(state_path, state)
        return
    if mutation == "pairing":
        state["paired_clients"] = {}
        state["client_properties"] = {}
        state["client_uuid_to_bytes"] = {}
        _write_json(state_path, state)
        return
    if mutation == "aid_iid":
        aids_path = directory / ".storage" / f"homekit.{entry_id}.aids"
        aids = json.loads(aids_path.read_text(encoding="utf-8"))
        allocation = aids["data"]["allocations"]["input_boolean.input_boolean.multi_bridge_a"]
        aids["data"]["allocations"]["input_boolean.input_boolean.multi_bridge_a"] = allocation + 1
        _write_json(aids_path, aids)
        return
    if mutation == "allowlist":
        entries_path = directory / ".storage" / "core.config_entries"
        entries = json.loads(entries_path.read_text(encoding="utf-8"))
        for entry in entries["data"]["entries"]:
            if entry.get("entry_id") == entry_id:
                entry["options"]["filter"]["include_entities"].append(
                    "input_boolean.multi_bridge_b"
                )
                break
        else:
            raise AssertionError("Bridge A Config Entry missing")
        _write_json(entries_path, entries)
        return
    if mutation == "duplicate":
        entries_path = directory / ".storage" / "core.config_entries"
        entries = json.loads(entries_path.read_text(encoding="utf-8"))
        for entry in entries["data"]["entries"]:
            if entry.get("entry_id") == entry_id:
                duplicate = json.loads(json.dumps(entry))
                duplicate["entry_id"] = "isolated-multi-bridge-a-duplicate-022"
                entries["data"]["entries"].append(duplicate)
                break
        else:
            raise AssertionError("Bridge A Config Entry missing")
        _write_json(entries_path, entries)
        return
    raise AssertionError(f"Unknown HAP mutation: {mutation}")


def _fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("direction", ["ui_to_yaml", "yaml_to_ui"])
@pytest.mark.parametrize("mutation", ["mac", "pairing", "aid_iid", "allowlist", "duplicate"])
def test_real_hap_mutation_is_blocked_before_bridge_publish(
    direction: str, mutation: str
) -> None:
    """A real persisted mutation must fail closed while Bridge B stays usable."""
    with TemporaryDirectory(prefix=f"hkm-core-hap-mutation-022-{direction}-{mutation}-") as directory:
        root = Path(directory)
        paired = _run(directory, direction, "pair")
        assert paired.returncode == 0, paired.stdout + paired.stderr
        bridge_b_state = _fingerprint(root / ".storage" / "homekit.isolated-multi-bridge-b-015.state")

        crashed = _run(directory, direction, "migrate")
        assert crashed.returncode == -9, crashed.stdout + crashed.stderr
        _mutate(root, mutation)

        observed = _run(directory, direction, "security_verify")
        assert observed.returncode == 0, observed.stdout + observed.stderr
        evidence = json.loads((root / "security-observation.json").read_text(encoding="utf-8"))

        migration = evidence["journal"]
        assert migration["state"] == "MANUAL_RECOVERY_REQUIRED", evidence
        assert migration["commit_status"] == "MANUAL_RECOVERY_REQUIRED", evidence
        expected_entries = 3 if mutation == "duplicate" else 2
        assert evidence["entry_count"] == expected_entries, evidence
        assert evidence["reconnect"]["Bridge A"]["ok"] is False, evidence
        assert evidence["reconnect"]["Bridge B"]["ok"] is True, evidence
        if mutation == "duplicate":
            assert evidence["active_bridge_count"] == 1, evidence
        assert _fingerprint(root / ".storage" / "homekit.isolated-multi-bridge-b-015.state") == bridge_b_state


def test_real_hap_allowlist_mutation_with_25_entity_fixture_is_blocked() -> None:
    """The actual large HAP fixture cannot expand after an allowlist mutation."""
    direction = "ui_to_yaml"
    with TemporaryDirectory(prefix="hkm-core-hap-allowlist-022-") as directory:
        root = Path(directory)
        env = dict(os.environ, HKM_CORE_MULTIBRIDGE_LARGE_ALLOWLIST="1")
        paired = _run_with_env(directory, direction, "pair", env)
        assert paired.returncode == 0, paired.stdout + paired.stderr
        crashed = _run_with_env(directory, direction, "migrate", env)
        assert crashed.returncode == -9, crashed.stdout + crashed.stderr
        _mutate(root, "allowlist")
        observed = _run_with_env(directory, direction, "security_verify", env)
        assert observed.returncode == 0, observed.stdout + observed.stderr
        evidence = json.loads((root / "security-observation.json").read_text(encoding="utf-8"))
        assert evidence["migration"]["state"] == "MANUAL_RECOVERY_REQUIRED", evidence
        assert evidence["reconnect"]["Bridge A"]["ok"] is False, evidence
        assert evidence["reconnect"]["Bridge B"]["ok"] is True, evidence


def _run_with_env(
    directory: str, direction: str, phase: str, extra: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    old = os.environ.copy()
    os.environ.update(extra)
    try:
        return _run(directory, direction, phase)
    finally:
        os.environ.clear()
        os.environ.update(old)
