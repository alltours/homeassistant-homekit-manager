"""Regression test for a real SOURCE_IMPORT HomeKit bootstrap."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
WORKER = Path(__file__).with_name("_yaml_import_bootstrap_worker_013.py")


def test_yaml_import_bootstrap_starts_real_source_import_bridge():
    with TemporaryDirectory(prefix="hkm-yaml-import-bootstrap-013-") as directory:
        environment = dict(
            os.environ,
            HKM_YAML_BOOTSTRAP_DIR=directory,
            PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
            PYTEST_ADDOPTS=(
                "-p pytest_asyncio.plugin -p pytest_socket "
                "-p pytest_homeassistant_custom_component.plugins"
            ),
        )
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", str(WORKER)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        identity = Path(directory, "public_identity.json")
        assert identity.is_file()
        assert '"source": "import"' in identity.read_text(encoding="utf-8")
