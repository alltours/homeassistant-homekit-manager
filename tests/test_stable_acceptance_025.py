"""Static release-gate assertions for the 0.10.31 release-candidate boundary."""

import json
from pathlib import Path

from custom_components.homekit_manager.const import INTEGRATION_VERSION
from custom_components.homekit_manager.migration import build_migration_matrix


ROOT = Path(__file__).resolve().parents[1]


def test_acceptance_version_and_release_manifest_are_consistent():
    manifest = json.loads(
        (ROOT / "custom_components/homekit_manager/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    release = json.loads(
        (ROOT / "docs/RELEASE_MANIFEST.json").read_text(encoding="utf-8")
    )
    assert manifest["version"] == package["version"] == INTEGRATION_VERSION
    assert release["integration_version"] == INTEGRATION_VERSION


def test_acceptance_native_migration_is_fail_closed():
    for plan in build_migration_matrix().values():
        assert plan["supported"] is False
        assert plan["changes_homekit"] is False
        assert plan["changes_pairings"] is False


def test_acceptance_release_manifest_contains_only_integration_files():
    release = json.loads(
        (ROOT / "docs/RELEASE_MANIFEST.json").read_text(encoding="utf-8")
    )
    paths = {item["path"] for item in release["files"]}
    assert paths
    assert all(not path.startswith(("../", "/")) for path in paths)
    assert all("experimental-core" not in path for path in paths)
    # The stable package may retain blocked migration/status code for
    # compatibility, but it must not contain test secrets, persistence data or
    # an experimental Core patch.
    assert all("pairing" not in path.lower() for path in paths)
    assert all(".storage" not in path.lower() for path in paths)
