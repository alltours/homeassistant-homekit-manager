"""Registry/UI denominator, availability, and bridge-context regressions."""
from types import SimpleNamespace as NS

from custom_components.homekit_manager.device_reconciliation import reconcile_devices
from custom_components.homekit_manager.diagnostics import build_diagnostics
from custom_components.homekit_manager.inventory import build_inventory


def entry(entity_id, device_id=None, disabled_by=None):
    return NS(entity_id=entity_id, device_id=device_id, area_id=None, name=None,
              original_name=None, platform="test", device_class=None,
              original_device_class=None, entity_category=None,
              disabled_by=disabled_by, hidden_by=None, config_entry_id="test")


def state(value):
    return NS(state=value, attributes={})


class Registry:
    def __init__(self, devices, composites=None):
        self.devices = devices
        self.child_devices = {}
        self.composites = composites or {}

    def async_get(self, device_id):
        return self.devices.get(device_id) or self.composites.get(device_id)


def test_synthetic_129_vs_121_is_composite_not_assumed_corruption():
    devices = {f"d{i}": NS(id=f"d{i}", name=f"D{i}", area_id=None, disabled_by=None,
                             is_composite_device=False) for i in range(121)}
    composites = {f"old{i}": NS(id=f"old{i}", name=f"Old{i}", area_id=None,
                                  disabled_by=None, is_composite_device=True) for i in range(8)}
    registry = Registry(devices, composites)
    entries = {f"sensor.e{i}": entry(f"sensor.e{i}", device_id)
               for i, device_id in enumerate([*devices, *composites])}
    inventory = build_inventory({"entities": entries}, registry, {},
                                {entity_id: state("42") for entity_id in entries})
    result = reconcile_devices((item.as_dict() for item in inventory), registry)
    assert result["referenced_device_count"] == 129
    assert result["registered_referenced_device_count"] == 121
    assert result["native_registry_device_count"] == 121
    assert result["composite_reference_ids"] == sorted(composites)
    assert result["missing_reference_ids"] == []


def test_six_exclusive_availability_states_and_missing_registry_evidence():
    devices = {"d": NS(id="d", name="Device", area_id=None, disabled_by=None)}
    registry = Registry(devices)
    entries = {f"sensor.{name}": entry(f"sensor.{name}", device_id, disabled)
               for name, device_id, disabled in (
                   ("available", "d", None), ("unavailable", "d", None),
                   ("unknown", "d", None), ("no_state", "d", None),
                   ("disabled", "d", "user"), ("orphaned", "gone", None))}
    states = {f"sensor.{name}": state(value) for name, value in (
        ("available", "42"), ("unavailable", "unavailable"),
        ("unknown", "unknown"), ("disabled", "42"), ("orphaned", "42"))}
    inventory = build_inventory({"entities": entries}, registry, {}, states)
    assert {item.entity_id.split(".")[1]: item.availability_status for item in inventory} == {
        "available": "available", "unavailable": "unavailable", "unknown": "unknown",
        "no_state": "no_state", "disabled": "disabled", "orphaned": "orphaned"}
    assert build_inventory({"entities": {"sensor.orphaned": entries["sensor.orphaned"]}},
                           None, {}, {"sensor.orphaned": state("42")})[0].availability_status == "available"
    devices["d"].disabled_by = "user"
    assert build_inventory({"entities": {"sensor.available": entries["sensor.available"]}},
                           registry, {}, {"sensor.available": state("42")})[0].availability_status == "disabled"


def test_diagnostics_follow_selected_bridge_filter_and_do_not_invent_publication():
    def item(entity_id, configured):
        return {"entity_id": entity_id, "available": True, "availability_status": "available",
                "compatibility": {"status": "unsupported", "reason": "no path"},
                "homekit": {"configured_by_filter": configured, "published": "unknown",
                            "apple_home_visible": "unknown"}}
    findings = build_diagnostics([item("sensor.out", False), item("sensor.in", True),
                                  item("sensor.undecided", None)], [], {"valid": True})
    severity = {finding["entity_id"]: finding["severity"] for finding in findings}
    assert severity == {"sensor.out": "info", "sensor.in": "critical", "sensor.undecided": "info"}
    assert all(finding["published"] == "unknown" and finding["apple_home_visible"] == "unknown"
               for finding in findings)
