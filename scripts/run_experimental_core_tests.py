"""Run tests only after proving that the pinned experimental Core is loaded.

This is intentionally fail-closed: a missing checkout, unexpected revision, or
missing Core-owned HomeKit migration boundary stops before pytest starts.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

EXPECTED_CAPABILITIES = (
    "async_prepare_source_migration",
    "async_switch_source",
    "async_recover_before_yaml_reconciliation",
    "async_get_migration_status",
    "async_request_rollback",
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
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
    result = subprocess.run(
        [sys.executable, "-c", probe],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-root", type=Path, default=os.environ.get("HKM_EXPERIMENTAL_CORE_ROOT"))
    parser.add_argument("--core-commit", default=os.environ.get("HKM_EXPERIMENTAL_CORE_COMMIT"))
    parser.add_argument("--core-version", default=os.environ.get("HKM_EXPERIMENTAL_CORE_VERSION"))
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.pytest_args[:1] == ["--"]:
        args.pytest_args = args.pytest_args[1:]
    if args.core_root is None:
        raise SystemExit("HKM_EXPERIMENTAL_CORE_ROOT or --core-root is required")
    manager_root = Path(__file__).resolve().parents[1]
    core_root = Path(args.core_root).expanduser().resolve()
    _verify_checkout(core_root, args.core_commit)
    probe = _probe_environment(manager_root, core_root, args.core_version)
    env = dict(os.environ)
    env.update(probe)
    env["HKM_EXPERIMENTAL_CORE_ROOT"] = str(core_root)
    if args.core_commit:
        env["HKM_EXPERIMENTAL_CORE_COMMIT"] = args.core_commit
    command = [sys.executable, "-m", "pytest", *args.pytest_args]
    return subprocess.run(command, cwd=manager_root, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
