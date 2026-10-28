"""The CI exception must remain exact and fail closed on scope changes."""

import json
from pathlib import Path

from scripts.audit_python_dependencies import evaluate, manager_pillow_imports


ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "scripts" / "python_audit_policy.json").read_text())


def _evaluate(report, *, core_version="2026.10.4", requirements=None, manager=None, imports=None):
    return evaluate(report, POLICY, core_version=core_version,
                    core_requirements=requirements if requirements is not None else ["Pillow==12.3.0"],
                    manager_requirements=manager if manager is not None else ["ruamel.yaml==0.18.17"],
                    pillow_imports=imports if imports is not None else [])


def test_known_platform_advisory_is_reported_but_other_finding_blocks():
    known = POLICY["accepted_platform_advisories"][0]
    report = {"dependencies": [
        {"name": "pillow", "version": "12.3.0", "vulns": [{"id": known}]},
        {"name": "ruamel-yaml", "version": "0.18.17", "vulns": []},
    ]}
    assert _evaluate(report) == ([known], [])
    report["dependencies"][1]["vulns"].append({"id": "GHSA-new-issue"})
    assert any("Unreviewed vulnerability" in error for error in _evaluate(report)[1])
    report["dependencies"][1]["vulns"].clear()
    report["dependencies"][0]["vulns"].append({"id": "GHSA-new-pillow-issue"})
    assert any("Unreviewed vulnerability" in error for error in _evaluate(report)[1])


def test_core_or_manager_scope_change_blocks():
    report = {"dependencies": [{"name": "pillow", "version": "12.3.0", "vulns": []}]}
    assert _evaluate(report, core_version="2026.11.0")[1]
    assert _evaluate(report, requirements=["Pillow==13.0.0"])[1]
    assert _evaluate(report, manager=["Pillow==12.3.0"])[1]
    assert _evaluate(report, imports=["custom_components/homekit_manager/image.py"])[1]
    assert _evaluate({"dependencies": [{"name": "pillow", "version": "13.0.0", "vulns": []}]})[1]


def test_manager_has_no_pillow_imports():
    assert manager_pillow_imports(ROOT) == []
