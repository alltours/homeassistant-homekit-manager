"""Contract tests for the safe 0.10.11 dual-mode surface."""

from custom_components.homekit_manager.dual_mode import (
    ADMIN_MODE_UI,
    ADMIN_MODE_YAML,
    build_dual_mode_status,
    build_mode_transition_plan,
    native_source_details,
)


def bridge(source="user", mode="bridge"):
    return {"entry_id": "bridge-1", "source": source, "mode": mode}


def test_native_source_labels_are_not_manager_mode_labels():
    assert native_source_details("user")["short_label"] == "UI / Bridge"
    assert native_source_details("import")["short_label"] == "YAML"
    assert native_source_details("user")["key"] != ADMIN_MODE_UI


def test_ui_source_exposes_yaml_as_draft_without_source_migration():
    result = build_dual_mode_status(
        bridge(), core_version="2026.11.0b0", yaml_valid=True, yaml_exists=False, snapshot_stale=False
    )
    assert result["administration_mode"] == ADMIN_MODE_UI
    yaml_plan = result["plans"][ADMIN_MODE_YAML]
    assert yaml_plan["status"] == "draft_only"
    assert yaml_plan["safe_action"] == "preview_export_validate"
    assert yaml_plan["can_execute"] is False
    assert yaml_plan["native_source_change"] is True
    assert result["source_migration"]["supported"] is False


def test_yaml_source_selects_yaml_and_keeps_same_source_plan_safe():
    result = build_dual_mode_status(
        bridge(source="import"), core_version="2026.11.0b0", yaml_valid=True, yaml_exists=True, snapshot_stale=False
    )
    assert result["administration_mode"] == ADMIN_MODE_YAML
    assert result["plans"][ADMIN_MODE_YAML]["status"] == "same_native_source"
    assert result["plans"][ADMIN_MODE_YAML]["native_source_change"] is False
    assert result["plans"][ADMIN_MODE_YAML]["pairing_preservation_proven"] is False


def test_invalid_existing_draft_blocks_yaml_plan_but_missing_draft_does_not():
    invalid = build_mode_transition_plan(
        "user", ADMIN_MODE_YAML, bridge_entry_id="bridge-1", bridge_mode="bridge",
        core_version="2026.11.0b0", yaml_valid=False, yaml_exists=True, snapshot_stale=False,
    )
    missing = build_mode_transition_plan(
        "user", ADMIN_MODE_YAML, bridge_entry_id="bridge-1", bridge_mode="bridge",
        core_version="2026.11.0b0", yaml_valid=False, yaml_exists=False, snapshot_stale=False,
    )
    assert invalid["status"] == "blocked"
    assert missing["status"] == "draft_only"


def test_stale_snapshot_blocks_both_mode_plans():
    result = build_dual_mode_status(
        bridge(), core_version="2026.11.0b0", yaml_valid=True, yaml_exists=True, snapshot_stale=True
    )
    assert all(plan["status"] == "blocked" for plan in result["plans"].values())
