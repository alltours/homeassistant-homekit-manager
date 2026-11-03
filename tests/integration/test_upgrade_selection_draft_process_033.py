"""Two-process upgrade and restart persistence acceptance for 0.10.33."""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path


def _archive_stable_component(repo: Path, destination: Path) -> None:
    git_executable = shutil.which("git")
    assert git_executable is not None
    archive_command = [
        git_executable, "archive", "--format=tar", "v0.10.32",
        "custom_components/homekit_manager",
    ]
    try:
        process = subprocess.run(  # noqa: S603
            archive_command, cwd=repo, check=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError:
        subprocess.run(  # noqa: S603
            [
                git_executable, "fetch", "--depth=1", "origin",
                "refs/tags/v0.10.32:refs/tags/v0.10.32",
            ],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        process = subprocess.run(  # noqa: S603
            archive_command, cwd=repo, check=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    with tarfile.open(fileobj=io.BytesIO(process.stdout), mode="r:") as archive:
        archive.extractall(destination, filter="data")


def _run_phase(repo: Path, worker: Path, config_dir: Path, component_root: Path, phase: str) -> None:
    environment = os.environ.copy()
    environment.update({
        "HKM_UPGRADE_PHASE": phase,
        "HKM_UPGRADE_CONFIG_DIR": str(config_dir),
        "PYTHONPATH": os.pathsep.join(
            [str(component_root), str(repo), str(repo / "tests" / "integration")]
        ),
    })
    subprocess.run(  # noqa: S603
        [sys.executable, str(worker)],
        cwd=repo,
        env=environment,
        check=True,
        timeout=90,
    )


def test_upgrade_and_draft_persistence_across_processes(tmp_path):
    repo = Path(__file__).parents[2]
    old_root = tmp_path / "stable-01032"
    old_root.mkdir()
    config_dir = tmp_path / "ha-config"
    _archive_stable_component(repo, old_root)
    worker = repo / "tests" / "integration" / "_selection_draft_restart_worker.py"

    _run_phase(repo, worker, config_dir, old_root, "legacy")
    _run_phase(repo, worker, config_dir, repo, "save")
    _run_phase(repo, worker, config_dir, repo, "restart")

    checkpoint = __import__("json").loads((config_dir / "upgrade_checkpoint.json").read_text())
    verified = __import__("json").loads((config_dir / "restart_verified.json").read_text())
    assert checkpoint["entry_id"] == "isolated-upgrade-bridge"
    assert verified == {
        "draft_reloaded": True,
        "entry_id": "isolated-upgrade-bridge",
        "native_options_unchanged": True,
        "write_enabled": False,
    }
