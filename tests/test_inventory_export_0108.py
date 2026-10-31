import csv
import json
import sys
import unittest
from io import StringIO
from pathlib import Path

# The export module has no HA runtime dependency. Avoid running the integration
# package initializer so this focused test remains runnable in a small venv.
package = "custom_components.homekit_manager"
if package not in sys.modules:
    module = type(sys)(package)
    module.__path__ = [str(Path(__file__).parents[1] / "custom_components" / "homekit_manager")]
    sys.modules[package] = module
from custom_components.homekit_manager.inventory_export import (  # noqa: E402 - package stub is installed first
    build_inventory_export,
    export_inventory_snapshot,
)


class InventoryExport0108Tests(unittest.TestCase):
    def rows(self):
        return [
            {
                "entity_id": "sensor.orphan",
                "name": "Orphan",
                "domain": "sensor",
                "device_id": None,
                "device_name": None,
                "area_id": None,
                "area_name": None,
                "integration_domain": "mqtt",
                "entity_category": "diagnostic",
                "hidden_by": None,
                "disabled_by": None,
                "device_disabled_by": None,
                "availability_status": "unavailable",
                "available": False,
                "state": "secret-state",
                "attributes": {"private": "secret"},
                "compatibility": {"status": "unsupported", "reason": "diagnostic"},
                "homekit": {"configured_by_filter": False, "filter_reason": "not_in_include", "runtime_publication": "unsupported"},
            },
            {
                "entity_id": "light.living",
                "name": "Living",
                "domain": "light",
                "device_id": "device-1",
                "device_name": "Lamp",
                "area_id": "area-1",
                "area_name": "Living",
                "integration_domain": "shelly",
                "entity_category": None,
                "hidden_by": None,
                "disabled_by": None,
                "device_disabled_by": None,
                "availability_status": "available",
                "available": True,
                "state": "on",
                "attributes": {"brightness": 255},
                "compatibility": {"status": "supported", "reason": "light"},
                "homekit": {"configured_by_filter": True, "filter_reason": "domain_include", "runtime_publication": "published_verified"},
            },
        ]

    def overview(self, complete=True):
        return {
            "selected_bridge_id": "bridge-1",
            "snapshot_timestamp": "2026-10-30T12:00:00+00:00",
            "snapshot_revision": 7,
            "snapshot_complete": complete,
            "snapshot_checks": {"expected_entity_count": 2, "inventory_entity_count": 2},
            "fingerprint": "abc123",
        }

    def test_json_is_deterministic_complete_and_value_free(self):
        document = {"bridges": {"bridge-1": {"entities": {"light.living": "include", "sensor.orphan": "exclude"}}}}
        snapshot = build_inventory_export(self.rows(), self.overview(), document, {"completeness": "verified"})
        encoded = export_inventory_snapshot(snapshot, "json")
        self.assertTrue(snapshot["complete"])
        decoded = json.loads(encoded)
        self.assertEqual([row["entity_id"] for row in decoded["entities"]], ["light.living", "sensor.orphan"])
        self.assertEqual(decoded["entities"][0]["manager_decision"], "include")
        self.assertEqual(decoded["entities"][1]["manager_decision"], "exclude")
        self.assertNotIn("state", encoded)
        self.assertNotIn("attributes", encoded)
        self.assertNotIn("secret", encoded)
        self.assertEqual(encoded, export_inventory_snapshot(snapshot, "json"))

    def test_csv_contains_orphan_entities_and_fixed_columns(self):
        snapshot = build_inventory_export(self.rows(), self.overview(), {"bridges": {}}, {})
        output = export_inventory_snapshot(snapshot, "csv")
        parsed = list(csv.DictReader(StringIO(output)))
        self.assertEqual([row["entity_id"] for row in parsed], ["light.living", "sensor.orphan"])
        self.assertEqual(parsed[1]["device_id"], "")
        self.assertIn("runtime_publication", parsed[0])

    def test_incomplete_snapshot_is_explicitly_marked(self):
        snapshot = build_inventory_export(self.rows(), self.overview(False), {"bridges": {}}, {})
        self.assertFalse(snapshot["complete"])
        self.assertFalse(json.loads(export_inventory_snapshot(snapshot))["complete"])

    def test_unknown_format_is_rejected(self):
        with self.assertRaises(ValueError):
            export_inventory_snapshot({}, "yaml")


if __name__ == "__main__":
    unittest.main()
