"""Isolated Core 2026.10.4 YAML examples; no live HomeKit reload."""
import pytest
from homeassistant.components.homekit import CONFIG_SCHEMA
from homeassistant.util.yaml.loader import load_yaml


@pytest.mark.parametrize("directive,fragment", [
    ("!include homekit.yaml", "- name: Kitchen Bridge\n  port: 21065\n  filter:\n    include_domains: [light]\n"),
    ("!include_dir_merge_list bridges", "- name: Kitchen Bridge\n  port: 21065\n  filter:\n    include_domains: [light]\n"),
])
def test_homekit_include_examples_validate_with_core_schema(tmp_path, directive, fragment):
    target = tmp_path / ("homekit.yaml" if directive.startswith("!include ") else "bridges/kitchen.yaml")
    target.parent.mkdir(exist_ok=True)
    target.write_text(fragment)
    root = tmp_path / "configuration.yaml"
    root.write_text(f"homekit: {directive}\n")
    config = load_yaml(root)
    validated = CONFIG_SCHEMA(config)
    assert validated["homekit"][0]["name"] == "Kitchen Bridge"
    assert validated["homekit"][0]["port"] == 21065


def test_duplicate_bridge_ports_fail_core_schema(tmp_path):
    root = tmp_path / "configuration.yaml"
    root.write_text("homekit:\n  - name: One Bridge\n    port: 21065\n"
                    "  - name: Two Bridge\n    port: 21065\n")
    with pytest.raises(Exception):
        CONFIG_SCHEMA(load_yaml(root))
