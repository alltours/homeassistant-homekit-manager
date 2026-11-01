"""Stable product boundary tests for 0.10.24."""

import json
from pathlib import Path

from custom_components.homekit_manager.const import INTEGRATION_VERSION
from custom_components.homekit_manager.migration import build_migration_matrix


ROOT = Path(__file__).resolve().parents[1]


def test_stable_version_metadata_is_consistent():
    manifest = json.loads(
        (ROOT / "custom_components/homekit_manager/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.10.24"
    assert manifest["version"] == INTEGRATION_VERSION == package["version"]


def test_native_source_migration_is_not_a_stable_capability():
    matrix = build_migration_matrix()
    for plan in matrix.values():
        assert plan["supported"] is False
        assert plan["changes_homekit"] is False
        assert plan["changes_pairings"] is False
        if plan["source"] != plan["target"]:
            assert plan["status"] == "blocked"


def test_experimental_core_patch_is_not_part_of_the_release_archive():
    tracked_release_files = {
        item["path"]
        for item in json.loads(
            (ROOT / "docs/RELEASE_MANIFEST.json").read_text(encoding="utf-8")
        )["files"]
    }
    assert not any(path.startswith("../") for path in tracked_release_files)
    assert all("experimental-core" not in path for path in tracked_release_files)
