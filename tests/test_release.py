"""Check release completeness and deterministic bytes, not just listed hashes."""
import importlib.util
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
