"""Give every real HA test its own filesystem; never share fixture YAML."""
import pytest


@pytest.fixture(autouse=True)
async def isolated_config_directory(hass, tmp_path):
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "configuration.yaml").write_text("# isolated HomeKit Manager test\n")
