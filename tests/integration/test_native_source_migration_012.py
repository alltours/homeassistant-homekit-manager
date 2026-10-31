"""End-to-end evidence for the unsupported native source migration POC."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
WORKER = Path(__file__).with_name("_native_source_migration_worker_012.py")


def test_internal_source_switch_preserves_isolated_hap_identity_across_restarts():
    """Exercise both directions without exposing a production migration path."""
    with TemporaryDirectory(prefix="hkm-native-source-migration-012-") as directory:
        for phase in (
            "pair_ui",
            "migrate_ui_yaml",
            "restart_yaml",
            "migrate_yaml_ui",
            "restart_ui",
        ):
            environment = dict(
                os.environ,
                HKM_NATIVE_SOURCE_MIGRATION_DIR=directory,
                HKM_NATIVE_SOURCE_MIGRATION_PHASE=phase,
            )
            # The parent beta runner disables auto-discovery because of its
            # Core/plugin compatibility adapter.  Keep that setting in the
            # child as well; the explicit plugins in inherited PYTEST_ADDOPTS
            # provide the HA fixtures without registering the plugin twice.
            environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
            required_plugins = (
                "-p pytest_asyncio.plugin -p pytest_socket "
                "-p pytest_homeassistant_custom_component.plugins"
            )
            if "pytest_homeassistant_custom_component.plugins" not in environment.get(
                "PYTEST_ADDOPTS", ""
            ):
                environment["PYTEST_ADDOPTS"] = (
                    f'{environment.get("PYTEST_ADDOPTS", "")} {required_plugins}'.strip()
                )
            result = subprocess.run(  # noqa: S603 - fixed local pytest worker
                [sys.executable, "-m", "pytest", "-q", str(WORKER)],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            assert result.returncode == 0, (
                f"Isolated native source migration phase {phase} failed "
                f"(exit {result.returncode})\nstdout={result.stdout}\nstderr={result.stderr}"
            )
