from custom_components.homekit_manager.config_source import detect_configuration_sources


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
