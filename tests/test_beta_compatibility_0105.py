"""Only explicitly reviewed Core versions receive a compatibility projection."""

from custom_components.homekit_manager.compatibility import classify_entity


def test_beta_and_future_versions_are_distinguished():
    light = {"domain": "light"}
    beta = classify_entity(light, core_version="2026.11.0b0")
    assert beta.status == "supported"
    assert beta.as_dict("2026.11.0b0")["core_reference"] == "2026.11.0b0"
    future = classify_entity(light, core_version="2026.11.1")
    assert future.status == "unknown"
    assert future.as_dict("2026.11.1")["core_reference"] is None


def test_new_beta_sensor_types_do_not_leak_into_stable_reference():
    for device_class, expected in [("ozone", "OzoneSensor"), ("sulphur_dioxide", "SulphurDioxideSensor")]:
        entity = {"domain": "sensor", "device_class": device_class, "attributes": {}}
        assert classify_entity(entity, core_version="2026.11.0b0").expected_type == expected
        assert classify_entity(entity, core_version="2026.10.4").status == "conditionally_supported"
