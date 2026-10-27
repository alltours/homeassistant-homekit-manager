from types import SimpleNamespace

from custom_components.homekit_manager.homekit_reader import read_homekit_entries


def test_lock_and_alarm_codes_never_leave_internal_reader():
    entry = SimpleNamespace(
        entry_id="test", title="Test", source="user", state=SimpleNamespace(value="loaded"),
        supports_options=True, supports_reconfigure=False,
        data={"name": "Test", "port": 21088},
        options={"entity_config": {"lock.front": {"code": "1234", "type": "lock"},
                                   "camera.front": {"video_codec": "copy"}}, "setup_code": "9999"},
    )
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_entries=lambda domain: [entry]))
    result = read_homekit_entries(hass)[0].as_dict()
    assert "code" not in result["options"]["entity_config"]["lock.front"]
    assert "setup_code" not in result["options"]
    assert result["options"]["entity_config"]["camera.front"]["video_codec"] == "copy"
