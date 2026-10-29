"""HA-facing names keep user overrides and current friendly names."""

from custom_components.homekit_manager.inventory import build_inventory


def test_entity_and_device_name_priority():
    entries = {
        "light.one": {"entity_id": "light.one", "device_id": "device", "name": None, "original_name": "Original"},
        "light.two": {"entity_id": "light.two", "device_id": "device", "name": "Von Nutzer benannt", "original_name": "Original"},
    }
    devices = {"device": {"name_by_user": "Decke", "name": "Technischer Gerätename", "area_id": "hall"}}
    areas = {"hall": {"name": "Flur"}}
    states = {"light.one": {"state": "on", "attributes": {"friendly_name": "Freundlicher Name"}},
              "light.two": {"state": "off", "attributes": {"friendly_name": "Anderer State-Name"}}}
    inventory = build_inventory(entries, devices, areas, states)
    assert [(item.name, item.device_name, item.area_name) for item in inventory] == [
        ("Freundlicher Name", "Decke", "Flur"), ("Von Nutzer benannt", "Decke", "Flur")
    ]
