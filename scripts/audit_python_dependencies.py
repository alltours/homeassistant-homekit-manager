"""Audit the full pinned Core runtime with one explicit platform risk decision.

The integration does not own Core's Pillow pin. The exact, reviewed Pillow
advisories remain visible in the report; every new finding fails this gate.
"""

from __future__ import annotations

import ast
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "scripts" / "python_audit_policy.json"
REPORT = ROOT / ".audit" / "python-runtime-audit.json"


def manager_pillow_imports(root: Path) -> list[str]:
    """Prevent a direct Pillow import from silently invalidating the decision."""
    hits = []
    for source in (root / "custom_components" / "homekit_manager").rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(alias.name == "PIL" or alias.name.startswith("PIL.") for alias in node.names):
                hits.append(str(source.relative_to(root)))
            elif isinstance(node, ast.ImportFrom) and node.module and (node.module == "PIL" or node.module.startswith("PIL.")):
                hits.append(str(source.relative_to(root)))
    return sorted(set(hits))


def evaluate(report: dict, policy: dict, *, core_version: str, core_requirements: list[str], manager_requirements: list[str], pillow_imports: list[str]) -> tuple[list[str], list[str]]:
    """Return accepted platform IDs and gate errors; never suppress evidence."""
    errors: list[str] = []
    accepted: list[str] = []
    if core_version != policy["core_version"]:
        errors.append(f"Core version changed: {core_version}")
    if policy["core_pin"] not in core_requirements:
        errors.append("Reviewed Pillow pin is not an exact Core requirement")
    if any("pillow" in requirement.lower() for requirement in manager_requirements):
        errors.append("Manager now declares Pillow directly")
    if pillow_imports:
        errors.append(f"Manager now imports Pillow: {pillow_imports}")
    dependencies = report.get("dependencies")
    if not isinstance(dependencies, list):
        return accepted, errors + ["pip-audit report has no dependency list"]
    seen = set()
    for dependency in dependencies:
        if not isinstance(dependency, dict) or not isinstance(dependency.get("vulns"), list):
            errors.append("Malformed pip-audit dependency entry")
            continue
        name = str(dependency.get("name", "")).lower().replace("_", "-")
        version = dependency.get("version")
        if name == "pillow":
            seen.add(name)
            if version != policy["pillow_version"]:
                errors.append(f"Pillow version changed: {version}")
        for vulnerability in dependency["vulns"]:
            identifier = vulnerability.get("id") if isinstance(vulnerability, dict) else None
            if not isinstance(identifier, str):
                errors.append(f"Malformed advisory for {name}")
            elif name == "pillow" and version == policy["pillow_version"] and identifier in policy["accepted_platform_advisories"]:
                accepted.append(identifier)
            else:
                errors.append(f"Unreviewed vulnerability: {name} {version} {identifier}")
    if "pillow" not in seen:
        errors.append("Pinned Core Pillow package is absent from audit")
    return sorted(accepted), errors


def main() -> int:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    REPORT.parent.mkdir(exist_ok=True)
    command = [sys.executable, "-m", "pip_audit", "--local", "--format", "json", "--progress-spinner", "off"]
    # Fixed interpreter and argument vector; no shell or untrusted command input.
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=180)  # noqa: S603
    if result.returncode not in (0, 1) or not result.stdout.strip():
        print(f"pip-audit failed without a usable report: {result.stderr.strip()}", file=sys.stderr)
        return 2
    REPORT.write_text(result.stdout, encoding="utf-8")
    try:
        report = json.loads(result.stdout)
        core = importlib.metadata.metadata("homeassistant")
        manager = json.loads((ROOT / "custom_components" / "homekit_manager" / "manifest.json").read_text(encoding="utf-8"))
        accepted, errors = evaluate(
            report, policy, core_version=importlib.metadata.version("homeassistant"),
            core_requirements=core.get_all("Requires-Dist", []),
            manager_requirements=manager["requirements"],
            pillow_imports=manager_pillow_imports(ROOT),
        )
    except (ValueError, KeyError, TypeError, importlib.metadata.PackageNotFoundError) as err:
        print(f"Audit policy evaluation failed: {err}", file=sys.stderr)
        return 2
    print(f"Full runtime audit: {len(accepted)} known Core Pillow advisories accepted as a documented platform risk; report: {REPORT}")
    for error in errors:
        print(f"BLOCKED: {error}", file=sys.stderr)
    if result.returncode == 1 and not accepted and not errors:
        print("pip-audit reported a failure without vulnerabilities", file=sys.stderr)
        return 2
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
