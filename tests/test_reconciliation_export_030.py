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
from custom_components.homekit_manager.selection_reconciliation import reconcile_selection  # noqa: E402


class ReconciliationExport030Tests(unittest.TestCase):
    @staticmethod
    def synthetic_entity(entity_id, *, configured=True, reason="explicit_include", device_id="device-1", area_id="area-1"):
        domain = entity_id.split(".", 1)[0]
        return {
            "entity_id": entity_id,
            "device_id": device_id,
            "device_name": "Testgerät" if device_id else None,
            "area_id": area_id,
            "area_name": "Testbereich" if area_id else None,
            "domain": domain,
            "compatibility": {"status": "supported"},
            "homekit": {"configured_by_filter": configured, "filter_reason": reason},
        }

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

    def test_production_category_shape_is_exactly_23_plus_6_and_separate(self):
        native_ids = [f"light.native_{index}" for index in range(23)]
        stale_ids = [f"sensor.deleted_{index}" for index in range(6)]
        inventory = [self.synthetic_entity(entity_id) for entity_id in native_ids]
        document = {"bridges": {"bridge-1": {
            "policy": "explicit_overrides",
            "entities": {entity_id: "exclude" for entity_id in stale_ids},
        }}}
        reconciliation = reconcile_selection(
            document,
            "bridge-1",
            inventory,
            {"include_entities": native_ids},
            {"state": "unknown", "entity_ids": []},
            {
                "completeness": "verified",
                "entity_status": {entity_id: "published_verified" for entity_id in native_ids},
                "accessories": [
                    {"entity_id": entity_id, "aid": index + 1, "iid_signature": f"iid-{index}"}
                    for index, entity_id in enumerate(native_ids)
                ],
            },
        )
        technical = [
            {"code": "selection_mismatch", "severity": "warning", "title": "Technical", "detail": "Technical"},
            *[{"code": "unsupported_entity", "severity": "warning", "title": "Unsupported", "detail": "Unsupported", "entity_id": f"sensor.unsupported_{index}"} for index in range(4)],
            *[{"code": "stale_filter_reference", "severity": "warning", "title": "Stale filter", "detail": "Stale filter", "entity_id": f"sensor.stale_{index}"} for index in range(2)],
        ]
        snapshot = build_reconciliation_export(
            {
                "integration_version": "0.10.30",
                "core_version": "2026.11.0b0",
                "snapshot_timestamp": "2026-11-02T12:00:00+00:00",
                "snapshot_revision": 1,
                "fingerprint": "synthetic",
                "selected_bridge_id": "bridge-1",
                "snapshot_complete": True,
                "configuration_alignment": reconciliation,
            },
            [{"entry_id": "bridge-1", "title": "Test", "source": "user", "state": "loaded", "mode": "bridge", "name": "Test", "port": 21063, "filter": {}}],
            {"findings": technical, "summary": {"total": len(technical)}},
            {
                "state": "verified", "completeness": "verified", "accessory_count": 23,
                "mapped_accessory_count": 23, "ambiguous_accessory_count": 0,
                "accessories": [{"entity_id": entity_id, "aid": index + 1, "mapping_source": "accessory.entity_id"} for index, entity_id in enumerate(native_ids)],
                "entity_status": {entity_id: "published_verified" for entity_id in native_ids},
                "ambiguous_accessories": [],
            },
        )
        rows = snapshot["reconciliation"]["deviations"]
        self.assertEqual(len(rows), 29)
        self.assertEqual(snapshot["summary"]["selection_deviation_categories"], {
            "native_explicit_unmanaged": 23,
            "stale_manager_decision": 6,
        })
        self.assertEqual(len(snapshot["technical_findings"]), 7)
        self.assertEqual(len(snapshot["runtime"]["entity_assignments"]), 23)
        self.assertTrue(snapshot["complete"])
        self.assertTrue(snapshot["completeness"]["complete"])
        csv_output = export_reconciliation_snapshot(snapshot, "csv")
        self.assertEqual(len(list(csv.DictReader(StringIO(csv_output["content"])))), 29)
        self.assertEqual(len(list(csv.DictReader(StringIO(csv_output["technical_content"])))), 7)
        self.assertEqual(len(list(csv.DictReader(StringIO(csv_output["runtime_content"])))), 23)
        self.assertEqual({row["entity_id"] for row in rows if row["entity_id"] in native_ids}, set(native_ids))
        self.assertEqual({row["entity_id"] for row in rows if row["entity_id"] in stale_ids}, set(stale_ids))

    def test_incomplete_snapshot_never_reports_complete(self):
        overview = self.snapshot()
        overview["snapshot_complete"] = False
        runtime = {
            "state": "partial", "completeness": "partial", "accessory_count": 1,
            "accessories": [{"entity_id": None, "aid": 7, "mapping_source": "unresolved"}],
            "ambiguous_accessories": [{"aid": 7}],
        }
        snapshot = build_reconciliation_export(
            overview,
            [{"entry_id": "bridge-1"}],
            {"findings": [], "summary": {}},
            runtime,
        )
        self.assertFalse(snapshot["completeness"]["snapshot_complete"])
        self.assertFalse(snapshot["completeness"]["runtime_complete"])
        self.assertFalse(snapshot["complete"])
        self.assertFalse(snapshot["completeness"]["complete"])


if __name__ == "__main__":
    unittest.main()
