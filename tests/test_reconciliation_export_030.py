import csv
import copy
import json
import sys
import unittest
from io import StringIO
from pathlib import Path

package = "custom_components.homekit_manager"
if package not in sys.modules:
    module = type(sys)(package)
    module.__path__ = [str(Path(__file__).parents[1] / "custom_components" / "homekit_manager")]
    sys.modules[package] = module

from custom_components.homekit_manager.inventory_export import (  # noqa: E402
    build_reconciliation_export,
    export_reconciliation_snapshot,
)


class ReconciliationExport030Tests(unittest.TestCase):
    def snapshot(self):
        overview = {
            "integration_version": "0.10.30",
            "core_version": "2026.11.0b0",
            "snapshot_timestamp": "2026-11-02T12:00:00+00:00",
            "snapshot_revision": 12,
            "fingerprint": "fingerprint",
            "selected_bridge_id": "bridge-1",
            "snapshot_complete": True,
            "configuration_alignment": {
                "scope": "manager_native_runtime_selection",
                "state": "mismatch",
                "policy": "explicit_overrides",
                "message": "Mismatch",
                "deviation_count": 2,
                "deviation_summary": {"native_explicit_unmanaged": 1, "stale_manager_decision": 1},
                "deviations": [
                    {
                        "entity_id": "light.living",
                        "classification": "native_explicit_unmanaged",
                        "deviation_type": "native_explicit_unmanaged",
                        "device_id": "device-1",
                        "device_name": "Lamp",
                        "area_id": "area-1",
                        "area_name": "Living",
                        "domain": "light",
                        "native_selection": True,
                        "manager_decision": None,
                        "runtime_selection": "published_verified",
                        "hap_publication_status": "published_verified",
                        "aid": 7,
                        "iid_signature": "iid",
                        "technical_cause": "Native selection",
                        "severity": "warning",
                        "recommendation": "Review",
                        "evidence_sources": ["runtime_hap_diagnosis"],
                        "verification_status": "VERIFIED",
                        "unavailable_fields": [],
                    },
                    {
                        "entity_id": "sensor.gone",
                        "classification": "stale_manager_decision",
                        "deviation_type": "stale_manager_decision",
                        "device_id": None,
                        "device_name": None,
                        "area_id": None,
                        "area_name": None,
                        "domain": "sensor",
                        "native_selection": None,
                        "manager_decision": "exclude",
                        "runtime_selection": "unknown",
                        "hap_publication_status": "unknown",
                        "aid": None,
                        "iid_signature": None,
                        "technical_cause": "Missing",
                        "severity": "critical",
                        "recommendation": "Review",
                        "evidence_sources": ["manager_draft"],
                        "verification_status": "NOT_VERIFIED",
                        "unavailable_fields": ["device_id", "device_name", "area_id", "area_name", "aid", "iid_signature"],
                    },
                ],
            },
        }
        bridges = [{
            "entry_id": "bridge-1", "title": "HomeKit Bridge", "source": "user", "state": "loaded",
            "mode": "bridge", "name": "HomeKit Bridge", "port": 21063,
            "filter": {"include_entities": ["light.living"]},
        }]
        diagnostics = {"findings": [{
            "code": "unsupported_entity", "severity": "critical", "title": "Unsupported",
            "detail": "Unsupported", "entity_id": "sensor.internal", "recommendation": "Exclude",
        }], "summary": {"total": 1, "unsupported_entity": 1}}
        runtime = {
            "state": "verified", "completeness": "verified", "accessory_count": 1,
            "mapped_accessory_count": 1, "ambiguous_accessory_count": 0,
            "hap_baseline": {"entry_id": "bridge-1", "mac": "AA:BB:CC:DD:EE:FF", "port": 21063, "pairing_status": "PAIRED"},
            "accessories": [{
                "entity_id": "light.living", "aid": 7, "name": "Lamp", "mapping_source": "accessory.entity_id",
                "service_count": 1, "characteristic_count": 2, "iid_signature": "iid",
            }],
            "entity_status": {"light.living": "published_verified"},
        }
        return build_reconciliation_export(overview, bridges, diagnostics, runtime)

    def test_json_contains_complete_separate_sections(self):
        snapshot = self.snapshot()
        encoded = export_reconciliation_snapshot(snapshot, "json")["content"]
        decoded = json.loads(encoded)
        self.assertEqual(len(decoded["reconciliation"]["deviations"]), 2)
        self.assertEqual(len(decoded["technical_findings"]), 1)
        self.assertEqual(len(decoded["runtime"]["entity_assignments"]), 1)
        self.assertEqual(decoded["bridge"]["port"], 21063)
        self.assertEqual(decoded["runtime"]["hap_baseline"]["pairing_status"], "PAIRED")
        self.assertNotIn("private_key", encoded)
        self.assertNotIn("pincode", encoded)

    def test_csv_separates_technical_and_runtime_rows_and_neutralises_formula(self):
        snapshot = self.snapshot()
        snapshot["reconciliation"]["deviations"][0]["technical_cause"] = "=HYPERLINK(\"https://example.invalid\")"
        output = export_reconciliation_snapshot(snapshot, "csv")
        deviations = list(csv.DictReader(StringIO(output["content"])))
        technical = list(csv.DictReader(StringIO(output["technical_content"])))
        runtime = list(csv.DictReader(StringIO(output["runtime_content"])))
        self.assertEqual(len(deviations), 2)
        self.assertTrue(deviations[0]["technical_cause"].startswith("'=HYPERLINK"))
        self.assertEqual(len(technical), 1)
        self.assertEqual(len(runtime), 1)

    def test_json_is_deterministic(self):
        snapshot = self.snapshot()
        self.assertEqual(
            export_reconciliation_snapshot(snapshot, "json")["content"],
            export_reconciliation_snapshot(snapshot, "json")["content"],
        )

    def test_export_is_pure_and_normalises_security_fields(self):
        overview = self.snapshot()
        source = copy.deepcopy(overview)
        exported = export_reconciliation_snapshot(overview, "json")["content"]
        decoded = json.loads(exported)
        self.assertEqual(overview, source)
        self.assertEqual(decoded["reconciliation"]["deviations"][0]["security_relevance"], "MEDIUM")


if __name__ == "__main__":
    unittest.main()
