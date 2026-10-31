"""Run the startup recovery boundary in a real isolated Core process."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
WORKER = Path(__file__).with_name("_startup_recovery_lifecycle_worker_013.py")


def test_full_core_start_reports_incomplete_migration_without_mutating_homekit():
    with TemporaryDirectory(prefix="hkm-startup-recovery-013-") as directory:
        environment = dict(
            os.environ,
            HKM_STARTUP_RECOVERY_DIR=directory,
            HKM_REPO_ROOT=str(ROOT),
            PYTHONPATH=os.pathsep.join(
                item for item in (str(ROOT), os.environ.get("PYTHONPATH", "")) if item
            ),
        )
        result = subprocess.run(
            [sys.executable, "-X", "faulthandler", str(WORKER)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=240,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        observed = Path(directory, "observed.json")
        assert observed.is_file()
        content = observed.read_text(encoding="utf-8")
        assert '"entry_count": 1' in content
        assert '"entry_source": "import"' in content
        assert '"native_mutation_allowed": false' in content
