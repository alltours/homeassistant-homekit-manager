"""Run tests only after proving that the pinned experimental Core is loaded.

This is intentionally fail-closed: a missing checkout, unexpected revision, or
missing Core-owned HomeKit migration boundary stops before pytest starts.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

EXPECTED_CAPABILITIES = (
    "async_prepare_source_migration",
    "async_switch_source",
    "async_recover_before_yaml_reconciliation",
    "async_get_migration_status",
    "async_request_rollback",
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(  # noqa: S603
        ["git", "-C", str(root), *args],  # noqa: S607 - fixed Git executable
        check=True,
        capture_output=True,
        text=True,
    )  # noqa: S603, S607 - fixed Git executable and validated local checkout
    return result.stdout.strip()


def _verify_checkout(root: Path, expected_commit: str | None) -> None:
    if not root.is_dir() or not (root / ".git").exists():
        raise SystemExit(f"Experimental Core checkout missing or not a Git checkout: {root}")
    actual_commit = _git(root, "rev-parse", "HEAD")
    if expected_commit and actual_commit != expected_commit:
        raise SystemExit(
            "Experimental Core commit mismatch: "
            f"expected {expected_commit}, loaded {actual_commit}"
        )
    migration = root / "homeassistant/components/homekit/migration.py"
    if not migration.is_file():
        raise SystemExit(f"Core migration boundary missing: {migration}")


def _verify_tree(root: Path, expected_tree: str | None) -> None:
    if not expected_tree:
        return
    actual_tree = _git(root, "write-tree")
    if actual_tree != expected_tree:
        raise SystemExit(f"Experimental Core tree mismatch: expected {expected_tree}, loaded {actual_tree}")


def _probe_environment(manager_root: Path, core_root: Path, expected_version: str | None) -> dict[str, str]:
    probe = (
        "import homeassistant, homeassistant.components.homekit.migration as migration; "
        "from homeassistant.const import __version__; "
        "print(homeassistant.__file__); print(__version__); "
        "print(migration.__file__); "
        f"missing=[name for name in {EXPECTED_CAPABILITIES!r} if not callable(getattr(migration, name, None))]; "
        "import sys; sys.exit('missing Core migration capabilities: '+','.join(missing)) if missing else None"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(core_root), str(manager_root)]
        + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", probe],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )  # noqa: S603 - probe is a fixed literal
    lines = result.stdout.splitlines()
    if len(lines) < 3:
        raise SystemExit("Core import probe returned incomplete evidence")
    core_file, core_version, migration_file = map(str, lines[:3])
    core_prefix = str(core_root.resolve()) + os.sep
    if not core_file.startswith(core_prefix) or not migration_file.startswith(core_prefix):
        raise SystemExit(
            "Imported Core module escaped the requested checkout: "
            f"homeassistant={core_file}, migration={migration_file}"
        )
    if expected_version and core_version != expected_version:
        raise SystemExit(f"Core version mismatch: expected {expected_version}, loaded {core_version}")
    print(f"verified experimental Core: {core_version} {core_root}")
    print(f"verified migration module: {migration_file}")
    return {"PYTHONPATH": env["PYTHONPATH"], "CORE_VERSION": core_version}


def _collect_count(command: list[str], cwd: Path, env: dict[str, str]) -> int:
    result = subprocess.run(  # noqa: S603 - command is assembled from reviewed pytest arguments
        command + ["--collect-only", "-q"], cwd=cwd, env=env, capture_output=True, text=True
    )
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    if result.returncode:
        raise SystemExit(f"experimental Core test collection failed with exit code {result.returncode}")
    match = re.search(r"(?:collected\s+|^)(\d+)(?:/\d+)?\s+tests? collected", result.stdout, re.MULTILINE)
    if not match:
        match = re.search(r"(\d+)/(\d+) tests collected", result.stderr)
    if not match or int(match.group(1)) <= 0:
        raise SystemExit("experimental Core suite collected no tests; refusing a vacuous pass")
    count = int(match.group(1))
    print(f"verified experimental test collection: {count} tests")
    return count


def _write_summary(path: Path, *, command: list[str], collected: int, returncode: int, junit: Path | None) -> None:
    summary: dict[str, object] = {
        "command": command,
        "collected": collected,
        "returncode": returncode,
        "status": "passed" if returncode == 0 else "failed",
    }
    if junit and junit.is_file():
        suite = ElementTree.parse(junit).getroot()  # noqa: S314 - local pytest JUnit evidence only
        suites = [suite] if suite.tag.endswith("testsuite") else list(suite)
        summary["tests"] = sum(int(item.attrib.get("tests", "0")) for item in suites)
        summary["failures"] = sum(int(item.attrib.get("failures", "0")) for item in suites)
        summary["errors"] = sum(int(item.attrib.get("errors", "0")) for item in suites)
        summary["skipped"] = sum(int(item.attrib.get("skipped", "0")) for item in suites)
        if summary["tests"] <= 0 or summary["skipped"]:
            raise SystemExit("experimental Core JUnit evidence is empty or contains skipped tests")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-root", type=Path, default=os.environ.get("HKM_EXPERIMENTAL_CORE_ROOT"))
    parser.add_argument("--core-commit", default=os.environ.get("HKM_EXPERIMENTAL_CORE_COMMIT"))
    parser.add_argument("--core-version", default=os.environ.get("HKM_EXPERIMENTAL_CORE_VERSION"))
    parser.add_argument("--expected-tree")
    parser.add_argument("--artifacts-dir", type=Path)
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.pytest_args[:1] == ["--"]:
        args.pytest_args = args.pytest_args[1:]
    if args.core_root is None:
        raise SystemExit("HKM_EXPERIMENTAL_CORE_ROOT or --core-root is required")
    manager_root = Path(__file__).resolve().parents[1]
    core_root = Path(args.core_root).expanduser().resolve()
    _verify_checkout(core_root, args.core_commit)
    _verify_tree(core_root, args.expected_tree)
    probe = _probe_environment(manager_root, core_root, args.core_version)
    env = dict(os.environ)
    env.update(probe)
    env["HKM_EXPERIMENTAL_CORE_ROOT"] = str(core_root)
    if args.core_commit:
        env["HKM_EXPERIMENTAL_CORE_COMMIT"] = args.core_commit
    command = [sys.executable, "-m", "pytest", *args.pytest_args]
    collected = _collect_count(command, manager_root, env)
    junit: Path | None = None
    if args.artifacts_dir:
        args.artifacts_dir.mkdir(parents=True, exist_ok=True)
        junit = args.artifacts_dir / "experimental-core.junit.xml"
        command.append(f"--junitxml={junit}")
        (args.artifacts_dir / "environment.json").write_text(
            json.dumps(
                {
                    "core_root": str(core_root),
                    "core_commit": args.core_commit,
                    "core_version": probe["CORE_VERSION"],
                    "python": sys.version,
                    "pytest_command": command,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    returncode = subprocess.run(  # noqa: S603 - command is assembled from reviewed pytest arguments
        command, cwd=manager_root, env=env, check=False
    ).returncode
    if args.artifacts_dir:
        _write_summary(
            args.artifacts_dir / "experimental-core-summary.json",
            command=command,
            collected=collected,
            returncode=returncode,
            junit=junit,
        )
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
