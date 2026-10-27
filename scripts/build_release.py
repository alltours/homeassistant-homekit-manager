#!/usr/bin/env python3
"""Build and verify byte-reproducible HACS archives from the canonical source."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("custom_components/homekit_manager")
MANIFEST = Path("docs/RELEASE_MANIFEST.json")
ALLOWED_SUFFIXES = {".py", ".json", ".js", ".svg", ".css", ".png"}


def release_manifest(root: Path = ROOT) -> dict:
    source = root / SOURCE
    version = json.loads((source / "manifest.json").read_text())["version"]
    constant = re.search(r'INTEGRATION_VERSION\s*=\s*["\']([^"\']+)', (source / "const.py").read_text())
    if not constant or constant[1] != version:
        raise ValueError("Python and integration versions disagree")
    if json.loads((root / "package.json").read_text())["version"] != version:
        raise ValueError("Frontend development version disagrees")
    files = []
    for path in sorted(source.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts:
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        if path.is_symlink() or path.suffix not in ALLOWED_SUFFIXES or " " in path.name:
            raise ValueError(f"Unexpected release file: {path.relative_to(root)}")
        content = path.read_bytes()
        files.append({"path": path.relative_to(source).as_posix(), "sha256": hashlib.sha256(content).hexdigest(), "size": len(content)})
    return {"integration_version": version, "file_count": len(files), "files": files}


def encoded(manifest: dict) -> bytes:
    return (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()


def verify_archive(path: Path, manifest: dict, root: Path = ROOT) -> None:
    with zipfile.ZipFile(path) as archive:
        expected = {f'{SOURCE}/{item["path"]}' for item in manifest["files"]} | {"RELEASE_MANIFEST.json"}
        if set(archive.namelist()) != expected or len(archive.namelist()) != len(expected):
            raise ValueError("Archive file list differs")
        if archive.read("RELEASE_MANIFEST.json") != encoded(manifest):
            raise ValueError("Archive manifest differs")
        for item in manifest["files"]:
            content = archive.read(f'{SOURCE}/{item["path"]}')
            if hashlib.sha256(content).hexdigest() != item["sha256"] or content != (root / SOURCE / item["path"]).read_bytes():
                raise ValueError(f'Archive/source mismatch: {item["path"]}')


def build(output: Path, root: Path = ROOT) -> Path:
    manifest = release_manifest(root)
    if (root / MANIFEST).read_bytes() != encoded(manifest):
        raise ValueError("Release manifest is stale; update it explicitly with --update-manifest")
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / f'homekit-manager-{manifest["integration_version"]}.zip'
    payload = {f'{SOURCE}/{item["path"]}': (root / SOURCE / item["path"]).read_bytes() for item in manifest["files"]}
    payload["RELEASE_MANIFEST.json"] = encoded(manifest)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(payload.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content, compresslevel=9)
    verify_archive(archive_path, manifest, root)
    return archive_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".release")
    parser.add_argument("--update-manifest", action="store_true")
    args = parser.parse_args()
    manifest = release_manifest()
    if args.update_manifest:
        (ROOT / MANIFEST).write_bytes(encoded(manifest))
    path = build(args.output)
    print(json.dumps({"archive": str(path), "version": manifest["integration_version"], "files": manifest["file_count"], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
