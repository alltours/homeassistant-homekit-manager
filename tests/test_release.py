"""Check release completeness and deterministic bytes, not just listed hashes."""
import compileall
import importlib.util
import json
from pathlib import Path
import shutil
import zipfile

import pytest

_spec = importlib.util.spec_from_file_location("build_release", Path(__file__).resolve().parents[1] / "scripts/build_release.py")
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)


def test_release_archive_matches_every_source_byte_and_is_reproducible(tmp_path):
    first = release.build(tmp_path / "one")
    second = release.build(tmp_path / "two")
    assert first.read_bytes() == second.read_bytes()
    manifest = release.release_manifest()
    release.verify_archive(first, manifest)
    with zipfile.ZipFile(first) as archive:
        assert all(item.date_time == (1980, 1, 1, 0, 0, 0) for item in archive.infolist())


def test_fresh_release_extraction_has_installable_structure_and_compiles(tmp_path):
    archive_path = release.build(tmp_path / "build")
    extracted = tmp_path / "fresh-extract"
    with zipfile.ZipFile(archive_path) as archive:
        assert all(name.startswith("custom_components/homekit_manager/") or name == "RELEASE_MANIFEST.json"
                   for name in archive.namelist())
        archive.extractall(extracted)
    extracted_manifest = json.loads((extracted / "RELEASE_MANIFEST.json").read_text())
    component = extracted / "custom_components" / "homekit_manager"
    assert extracted_manifest["integration_version"] == json.loads((component / "manifest.json").read_text())["version"]
    assert len(list(component.rglob("*.py"))) > 10
    assert (component / "www" / "homekit-manager.js").is_file()
    assert compileall.compile_dir(component, quiet=1)
    for item in component.rglob("*.json"):
        json.loads(item.read_text())


def test_release_rejects_stale_manifest_and_unexpected_source_files(tmp_path):
    shutil.copytree(release.ROOT / release.SOURCE, tmp_path / release.SOURCE, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(release.ROOT / "package.json", tmp_path)
    (tmp_path / "docs").mkdir()
    shutil.copy(release.ROOT / release.MANIFEST, tmp_path / release.MANIFEST)
    (tmp_path / release.SOURCE / "const.py").write_text((tmp_path / release.SOURCE / "const.py").read_text() + "\n# changed\n")
    with pytest.raises(ValueError, match="manifest is stale"):
        release.build(tmp_path / "output", tmp_path)
    (tmp_path / release.SOURCE / "untracked copy.js").write_text("invalid duplicate")
    with pytest.raises(ValueError, match="Unexpected release file"):
        release.release_manifest(tmp_path)
