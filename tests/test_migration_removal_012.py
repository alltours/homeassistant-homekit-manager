"""Regression coverage for the source-migration removal boundary."""
from __future__ import annotations

from pathlib import Path

from custom_components.homekit_manager.config_source import detect_configuration_sources
from custom_components.homekit_manager.const import INTEGRATION_VERSION

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "homekit_manager"


def test_source_migration_engine_and_experimental_core_assets_are_removed():
    removed_modules = {
        "core_migration.py",
        "dual_mode.py",
        "migration.py",
        "migration_engine.py",
        "migration_journal.py",
        "migration_lock.py",
        "migration_recovery.py",
        "migration_snapshot.py",
        "migration_store.py",
        "mode_store.py",
        "startup_recovery.py",
    }
    assert not any((COMPONENT / name).exists() for name in removed_modules)
    assert not (ROOT / ".github" / "workflows" / "experimental-core.yml").exists()
    assert not (ROOT / ".ci" / "experimental-core").exists()


def test_removed_source_commands_are_not_present_in_runtime_modules():
    websocket_source = (COMPONENT / "websocket.py").read_text(encoding="utf-8")
    const_source = (COMPONENT / "const.py").read_text(encoding="utf-8")
    for command in ("migration_plan", "migration_status", "migration_start", "set_mode"):
        assert command not in websocket_source
        assert command not in const_source


def test_yaml_bridge_detection_remains_available_without_source_migration():
    result = detect_configuration_sources(
        "homekit:\n  - name: Existing YAML Bridge\n",
        manager_file_exists=False,
        bridge_count=0,
    )
    assert result["active_mode"] == "yaml"
    assert result["sources"] == ["yaml"]
    assert result["direct_yaml"] is True


def test_release_version_is_101():
    assert INTEGRATION_VERSION == "1.0.1"
