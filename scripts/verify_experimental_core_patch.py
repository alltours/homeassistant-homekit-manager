"""Verify and apply the pinned experimental Home Assistant Core patch.

This verifier is deliberately independent of pytest.  It refuses to apply a
patch when the checkout, digest, changed-file set, or resulting Git tree does
not match the reviewed manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(  # noqa: S603
        ["git", "-C", str(root), *args],  # noqa: S607 - fixed Git executable
        check=True,
        capture_output=True,
        text=True,
    )  # noqa: S603, S607 - fixed Git executable and validated local checkout
    return result.stdout.strip()


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise SystemExit(f"cannot read experimental Core manifest: {path}: {err}") from err
    required = {
        "schema_version",
        "core_version",
        "base_commit",
        "target_commit",
        "target_tree",
        "patch_file",
        "patch_sha256",
        "changed_files",
    }
    missing = required - manifest.keys()
    if missing or manifest.get("schema_version") != 1:
        raise SystemExit(f"invalid experimental Core manifest: missing={sorted(missing)}")
    return manifest


def _verify_patch_digest(patch: Path, expected: str) -> str:
    actual = _digest(patch)
    if actual != expected:
        raise SystemExit(
            f"experimental Core patch SHA-256 mismatch: expected {expected}, loaded {actual}"
        )
    return actual


def verify_and_apply(core_root: Path, manifest_path: Path, patch_path: Path, evidence: Path) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    if not core_root.is_dir() or not (core_root / ".git").exists():
        raise SystemExit(f"experimental Core checkout missing or not a Git checkout: {core_root}")
    if not patch_path.is_file():
        raise SystemExit(f"experimental Core patch missing: {patch_path}")

    expected_base = str(manifest["base_commit"])
    actual_head = _git(core_root, "rev-parse", "HEAD")
    if actual_head != expected_base:
        raise SystemExit(
            f"experimental Core base mismatch: expected {expected_base}, loaded {actual_head}"
        )
    if _git(core_root, "status", "--porcelain"):
        raise SystemExit("experimental Core checkout is not clean before patch application")

    patch_digest = _verify_patch_digest(patch_path, str(manifest["patch_sha256"]))
    subprocess.run(  # noqa: S603, S607 - fixed Git executable and reviewed local patch path
        ["git", "-C", str(core_root), "apply", "--check", str(patch_path)],  # noqa: S607 - fixed Git executable
        check=True,
    )
    subprocess.run(  # noqa: S603, S607 - fixed Git executable and reviewed local patch path
        ["git", "-C", str(core_root), "apply", str(patch_path)],  # noqa: S607 - fixed Git executable
        check=True,
    )

    expected_files = sorted(str(value) for value in manifest["changed_files"])
    subprocess.run(  # noqa: S603, S607 - fixed Git executable and isolated checkout
        ["git", "-C", str(core_root), "add", "--all"],  # noqa: S607 - fixed Git executable
        check=True,
    )
    actual_files = sorted(_git(core_root, "diff", "--cached", "--name-only", expected_base).splitlines())
    if actual_files != expected_files:
        raise SystemExit(
            "experimental Core changed-file manifest mismatch: "
            f"expected {expected_files}, loaded {actual_files}"
        )
    if _git(core_root, "ls-files", "--others", "--exclude-standard"):
        raise SystemExit("unexpected untracked files appeared in experimental Core checkout")

    actual_tree = _git(core_root, "write-tree")
    expected_tree = str(manifest["target_tree"])
    if actual_tree != expected_tree:
        raise SystemExit(
            f"experimental Core tree mismatch: expected {expected_tree}, loaded {actual_tree}"
        )

    evidence.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "schema_version": 1,
        "core_version": manifest["core_version"],
        "base_commit": expected_base,
        "target_commit": manifest["target_commit"],
        "base_head_loaded": actual_head,
        "target_tree": actual_tree,
        "patch_sha256": patch_digest,
        "patch": str(patch_path.resolve()),
        "manifest": str(manifest_path.resolve()),
        "changed_files": expected_files,
        "status": "verified_and_applied",
    }
    evidence.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-root", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--patch", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = _load_manifest(args.manifest)
    patch = args.patch or args.manifest.parent / str(manifest["patch_file"])
    if args.verify_only:
        digest = _verify_patch_digest(patch.resolve(), str(manifest["patch_sha256"]))
        print(json.dumps({"patch_sha256": digest, "status": "verified"}, sort_keys=True))
        return 0
    if args.core_root is None:
        parser.error("--core-root is required unless --verify-only is used")
    verify_and_apply(args.core_root.resolve(), args.manifest.resolve(), patch.resolve(), args.evidence.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
