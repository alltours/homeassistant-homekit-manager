"""Independent security-oracle negative controls for experimental Core CI.

These tests intentionally mutate synthetic observations, never the product or a
real pairing.  They verify that the independent assertions reject the eight
security-critical conditions required by the CI gate.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
PATCH = ROOT / ".ci/experimental-core/hkm-core-2026.10.4-0.10.20.patch"
MANIFEST = ROOT / ".ci/experimental-core/manifest.json"
VERIFY = ROOT / "scripts/verify_experimental_core_patch.py"


def _baseline() -> dict[str, object]:
    return {
        "entry_id": "entry-a",
        "mac": "AA:BB:CC:DD:EE:01",
        "port": 21063,
        "pairing_fingerprint": "pair-a",
        "aids": [1, 2, 3],
        "iids": [1, 2, 3, 4, 5],
        "allowlist": [f"light.allowed_{index}" for index in range(25)],
        "accessories": [f"light.allowed_{index}" for index in range(25)],
        "bridge_count": 2,
        "fault_point": "AFTER_SOURCE_MUTATION",
    }


def _assert_identity(baseline: dict[str, object], observed: dict[str, object]) -> None:
    for key in ("entry_id", "mac", "port", "pairing_fingerprint", "aids", "iids"):
        assert observed[key] == baseline[key], f"HAP identity invariant violated: {key}"


def _assert_allowlist(baseline: dict[str, object], observed: dict[str, object]) -> None:
    assert observed["accessories"] == baseline["allowlist"], "published entity set changed"


def _assert_bridge_count(observed: dict[str, object]) -> None:
    assert observed["bridge_count"] == 2, "unexpected additional logical bridge"


def _assert_fault_reached(observed: dict[str, object], expected: str) -> None:
    assert observed.get("fault_point") == expected, "requested fault point was not reached"


def test_negative_control_positive_baseline_is_accepted() -> None:
    baseline = _baseline()
    _assert_identity(baseline, baseline)
    _assert_allowlist(baseline, baseline)
    _assert_bridge_count(baseline)
    _assert_fault_reached(baseline, "AFTER_SOURCE_MUTATION")


@pytest.mark.parametrize(
    ("mutation", "oracle"),
    [
        (lambda value: value.update(mac="AA:BB:CC:DD:EE:99"), _assert_identity),
        (lambda value: value.update(pairing_fingerprint="replacement-pairing"), _assert_identity),
        (lambda value: value.update(aids=[1, 2, 9]), _assert_identity),
        (lambda value: value.update(iids=[1, 2, 3, 4, 99]), _assert_identity),
        (
            lambda value: value.update(accessories=[*value["accessories"], "light.excluded_0"]),
            _assert_allowlist,
        ),
        (lambda value: value.update(bridge_count=3), _assert_bridge_count),
        (lambda value: value.update(fault_point=None), lambda value: _assert_fault_reached(value, "AFTER_SOURCE_MUTATION")),
    ],
    ids=["mac", "pairing", "aid", "iid", "allowlist", "duplicate-bridge", "fault-point"],
)
def test_negative_controls_reject_security_mutations(mutation, oracle) -> None:
    baseline = _baseline()
    observed = dict(baseline)
    mutation(observed)
    with pytest.raises(AssertionError):
        oracle(baseline, observed) if oracle in {_assert_identity, _assert_allowlist} else oracle(observed)


def test_negative_control_wrong_core_fails_before_pytest(tmp_path: Path) -> None:
    core = tmp_path / "core"
    core.mkdir()
    subprocess.run(["git", "init", "-q", str(core)], check=True)  # noqa: S603, S607 - isolated temp Git repo
    subprocess.run(["git", "-C", str(core), "config", "user.email", "ci@example.invalid"], check=True)  # noqa: S603, S607
    subprocess.run(["git", "-C", str(core), "config", "user.name", "CI"], check=True)  # noqa: S603, S607
    (core / "README").write_text("wrong core\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(core), "add", "README"], check=True)  # noqa: S603, S607
    subprocess.run(["git", "-C", str(core), "commit", "-qm", "wrong core"], check=True)  # noqa: S603, S607
    result = subprocess.run(  # noqa: S603 - fixed Python entry point and reviewed arguments
        [
            sys.executable,
            str(ROOT / "scripts/run_experimental_core_tests.py"),
            "--core-root",
            str(core),
            "--core-commit",
            "0" * 40,
            "--core-version",
            "2026.10.4",
            "tests",
            "-m",
            "experimental_core",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "commit mismatch" in result.stderr + result.stdout


def test_negative_control_tampered_patch_fails_digest(tmp_path: Path) -> None:
    tampered = tmp_path / PATCH.name
    tampered.write_bytes(PATCH.read_bytes() + b"\n# tampered\n")
    result = subprocess.run(  # noqa: S603 - fixed Python entry point and reviewed arguments
        [
            sys.executable,
            str(VERIFY),
            "--verify-only",
            "--manifest",
            str(MANIFEST),
            "--patch",
            str(tampered),
            "--evidence",
            str(tmp_path / "evidence.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "SHA-256 mismatch" in result.stderr + result.stdout
    assert hashlib.sha256(tampered.read_bytes()).hexdigest() != json.loads(MANIFEST.read_text())["patch_sha256"]
