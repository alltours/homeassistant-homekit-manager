"""Isolate real HA tests in filesystems and ports."""
import os
from pathlib import Path

import pytest
from port_allocator import release_http_port, reserve_http_port

# Integration tests exercise the same private-file contract as the production
# YAML/write-grant path.  Establish it before any test-created source files
# exist; individual fixtures still restore the process umask after each test.
os.umask(0o077)


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir):
    """Give every HA fixture a unique HTTP port and isolated configuration."""
    config_dir = Path(hass_tmp_config_dir)
    port = reserve_http_port(str(config_dir))
    configuration = config_dir / "configuration.yaml"
    existing = configuration.read_text(encoding="utf-8") if configuration.exists() else ""
    if "\nhttp:\n" not in f"\n{existing}":
        existing = f"{existing.rstrip()}\nhttp:\n  server_port: {port}\n"
    else:
        raise RuntimeError("Test fixture already defines http; use an explicit isolated port")
    configuration.write_text(existing, encoding="utf-8")
    try:
        yield str(config_dir)
    finally:
        release_http_port(port)


@pytest.fixture(autouse=True)
async def isolated_config_directory(hass, tmp_path):
    # pytest's temporary-directory mode is platform/runner dependent.  The
    # write-grant tests intentionally require a private configuration
    # directory, so make that precondition explicit instead of relying on the
    # process umask or the runner implementation.
    previous_umask = os.umask(0o077)
    try:
        tmp_path.chmod(0o700)
        hass.config.config_dir = str(tmp_path)
        (tmp_path / "configuration.yaml").write_text("# isolated HomeKit Manager test\n")
        yield
    finally:
        os.umask(previous_umask)
