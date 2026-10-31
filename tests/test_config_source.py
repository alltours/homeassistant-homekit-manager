from custom_components.homekit_manager.config_source import (
    detect_configuration_sources,
    inspect_configuration_sources,
)


def test_detects_config_entry_source():
    result = detect_configuration_sources("", manager_file_exists=False, bridge_count=1)
    assert result["active_mode"] == "homekit_bridge"
    assert result["ambiguous"] is False


def test_detects_manager_include_and_marks_bridge_mix_ambiguous():
    result = detect_configuration_sources(
        "homekit: !include homekit_manager.yaml\n",
        manager_file_exists=True,
        bridge_count=1,
    )
    assert result["mixed"] is True
    assert result["ambiguous"] is True
    assert "homekit_manager" in result["sources"]


def test_unknown_source_is_not_presented_as_standard():
    result = detect_configuration_sources("logger:\n  default: info\n", manager_file_exists=False, bridge_count=0)
    assert result["active_mode"] == "unknown"
    assert result["ambiguous"] is True


def test_non_manager_include_is_not_silently_normalized():
    result = detect_configuration_sources(
        "homekit: !include packages/homekit.yaml\n",
        manager_file_exists=False,
        bridge_count=0,
    )
    assert result["mixed"] is True
    assert result["sources"] == ["yaml_include"]


def test_inspects_include_without_exposing_file_content(tmp_path):
    included = tmp_path / "packages" / "homekit.yaml"
    included.parent.mkdir()
    included.write_text("homekit:\n  filter: {}\n", encoding="utf-8")
    result = inspect_configuration_sources(
        "homekit: !include packages/homekit.yaml\n",
        config_dir=tmp_path,
        manager_file_exists=False,
        bridge_count=0,
    )
    assert result["includes_readable"] is True
    assert result["include_files"][0]["path"] == "packages/homekit.yaml"
    assert "content" not in result["include_files"][0]


def test_rejects_include_outside_config_directory(tmp_path):
    result = inspect_configuration_sources(
        "homekit: !include ../secrets.yaml\n",
        config_dir=tmp_path,
        manager_file_exists=False,
        bridge_count=0,
    )
    assert result["includes_readable"] is False
    assert result["include_errors"]


def test_missing_manager_include_is_not_reported_as_active(tmp_path):
    result = inspect_configuration_sources(
        "homekit: !include homekit_manager.yaml\n",
        config_dir=tmp_path,
        manager_file_exists=False,
        bridge_count=0,
    )
    assert result["active_mode"] == "unknown"
    assert result["ambiguous"] is True


def test_detects_directory_merge_include_as_yaml_include():
    result = detect_configuration_sources(
        "homekit: !include_dir_merge_list bridges\n",
        manager_file_exists=False,
        bridge_count=0,
    )
    assert result["sources"] == ["yaml_include"]
    assert result["direct_yaml"] is False
    assert result["ambiguous"] is False


def test_inspects_directory_merge_include_deterministically(tmp_path):
    included = tmp_path / "bridges"
    included.mkdir()
    (included / "b.yaml").write_text("- name: B\n  port: 21066\n", encoding="utf-8")
    (included / "a.yaml").write_text("- name: A\n  port: 21065\n", encoding="utf-8")

    result = inspect_configuration_sources(
        "homekit: !include_dir_merge_list bridges\n",
        config_dir=tmp_path,
        manager_file_exists=False,
        bridge_count=0,
    )

    assert result["active_mode"] == "yaml_include"
    assert result["includes_readable"] is True
    assert result["include_files"][0]["kind"] == "directory"
    assert [member["path"] for member in result["include_files"][0]["members"]] == [
        "bridges/a.yaml",
        "bridges/b.yaml",
    ]


def test_rejects_symlink_in_directory_merge_include(tmp_path):
    included = tmp_path / "bridges"
    included.mkdir()
    target = tmp_path / "outside.yaml"
    target.write_text("- name: Outside\n  port: 21067\n", encoding="utf-8")
    (included / "linked.yaml").symlink_to(target)

    result = inspect_configuration_sources(
        "homekit: !include_dir_merge_named bridges\n",
        config_dir=tmp_path,
        manager_file_exists=False,
        bridge_count=0,
    )

    assert result["includes_readable"] is False
    assert result["include_errors"]


def test_directory_merge_matches_core_yaml_file_selection(tmp_path):
    included = tmp_path / "bridges" / "nested"
    included.mkdir(parents=True)
    (included / "bridge.yaml").write_text(
        "- name: Nested\n  port: 21069\n", encoding="utf-8"
    )
    (included / "notes.txt").write_text("not a Home Assistant source", encoding="utf-8")
    (included / "secrets.yaml").write_text("password: ignored\n", encoding="utf-8")
    (included / ".hidden.yaml").write_text("- ignored\n", encoding="utf-8")

    result = inspect_configuration_sources(
        "homekit: !include_dir_merge_list bridges\n",
        config_dir=tmp_path,
        manager_file_exists=False,
        bridge_count=0,
    )

    assert result["includes_readable"] is True
    assert [member["path"] for member in result["include_files"][0]["members"]] == [
        "bridges/nested/bridge.yaml"
    ]


def test_rejects_symlink_include_target(tmp_path):
    target = tmp_path / "real.yaml"
    target.write_text("- name: Real\n  port: 21068\n", encoding="utf-8")
    (tmp_path / "bridges.yaml").symlink_to(target)

    result = inspect_configuration_sources(
        "homekit: !include bridges.yaml\n",
        config_dir=tmp_path,
        manager_file_exists=False,
        bridge_count=0,
    )

    assert result["includes_readable"] is False
    assert result["include_files"][0]["symlink"] is True
