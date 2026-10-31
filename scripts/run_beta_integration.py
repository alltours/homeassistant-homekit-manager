"""Run the complete isolated integration suite against Core 2026.11.0b0.

The pinned pytest helper currently imports a logger hook removed by the beta
Core. The adapter is deliberately limited to that import compatibility and
does not modify Home Assistant source or bypass any test assertion.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "tests" / "integration" / "_beta_pytest_adapter"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ADAPTER))
import sitecustomize  # noqa: E402, F401 - load the documented test adapter


pythonpath = os.environ.get("PYTHONPATH")
paths = [str(ROOT), str(ADAPTER)]
if pythonpath:
    paths.append(pythonpath)
os.environ["PYTHONPATH"] = os.pathsep.join(paths)
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
os.environ["PYTEST_ADDOPTS"] = (
    "-p pytest_asyncio.plugin -p pytest_socket "
    "-p pytest_homeassistant_custom_component.plugins"
)

import pytest  # noqa: E402


raise SystemExit(
    pytest.main(
        [
            "-q",
            "tests/integration",
            "--disable-warnings",
            "--maxfail=1",
            "-p",
            "pytest_asyncio.plugin",
            "-p",
            "pytest_socket",
            "-p",
            "pytest_homeassistant_custom_component.plugins",
        ]
    )
)
