from custom_components.homekit_manager.const import MODE_HOMEKIT_BRIDGE, MODE_HOMEKIT_MANAGER, MODE_YAML
from custom_components.homekit_manager.migration import build_migration_matrix, build_migration_plan, completed_verification


def test_all_storage_directions_are_explicit():
    matrix = build_migration_matrix()
    assert len(matrix) == 9
    for source in (MODE_HOMEKIT_BRIDGE, MODE_YAML, MODE_HOMEKIT_MANAGER):
        for target in (MODE_HOMEKIT_BRIDGE, MODE_YAML, MODE_HOMEKIT_MANAGER):
            item = matrix[f"{source}->{target}"]
            assert item["changes_homekit"] is False
            assert item["changes_pairings"] is False
            assert item["supported"] is (source == target)


def test_cross_source_migration_is_blocked_with_core_reason():
    plan = build_migration_plan(MODE_YAML, MODE_HOMEKIT_BRIDGE, "bridge-1")
    assert plan["status"] == "blocked"
    assert plan["progress_mode"] == "indeterminate"
    assert "keine stabile öffentliche API" in plan["reason"]
    assert plan["bridge_entry_id"] == "bridge-1"


def test_same_source_is_read_only_verification():
    plan = build_migration_plan(MODE_HOMEKIT_BRIDGE, MODE_HOMEKIT_BRIDGE, "bridge-1")
    status = completed_verification(plan, "bridge-1")
    assert status["state"] == "completed"
    assert status["changed"] is False
    assert status["migration_performed"] is False
