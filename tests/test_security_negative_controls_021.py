"""Independent security-oracle negative controls for HomeKit state changes.

These tests intentionally mutate synthetic observations, never the product or a
real pairing. They verify that the independent assertions reject the
security-critical identity, allow-list, bridge-isolation and fault conditions.
"""
from __future__ import annotations

import pytest


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
