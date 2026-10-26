import ast
import sys
import unittest
import tempfile
import threading
import asyncio
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0, ".")

from custom_components.homekit_manager.compatibility import classify_entity
from custom_components.homekit_manager.filtering import build_core_filter, evaluate_filter
from custom_components.homekit_manager.inventory import build_inventory
from custom_components.homekit_manager.draft import serialize_draft
from custom_components.homekit_manager.yaml_store import YamlStore, YamlValidationError, YamlVersionConflict, YamlWriteError
from custom_components.homekit_manager.change_planner import plan_changes
from custom_components.homekit_manager.homekit_writer import HomeKitWriter, HomeKitWriteBlocked, HomeKitWriteDisabled, build_options_diff
from custom_components.homekit_manager.reconcile import reconcile_desired_state
from custom_components.homekit_manager.exporter import export_desired_state
from custom_components.homekit_manager.homekit_reader import read_homekit_entries
from custom_components.homekit_manager.grouping import build_area_views, build_device_views
from custom_components.homekit_manager.diagnostics import build_diagnostics, diagnostics_summary
from custom_components.homekit_manager.device_config import build_preview
from custom_components.homekit_manager.rules import evaluate_rules
from custom_components.homekit_manager.history import compare_history, make_history_entry, restore_as_draft
from custom_components.homekit_manager.performance import summarize_inventory

class HomeKitManagerTests(unittest.TestCase):
    def setUp(self):
        self.entities = [
            SimpleNamespace(entity_id="light.flur_decke", name="Flur Decke", original_name=None, device_id="d1", area_id=None, platform="shelly", device_class=None, original_device_class=None, entity_category=None, disabled_by=None, hidden_by=None, config_entry_id="e1"),
            SimpleNamespace(entity_id="sensor.temp", name=None, original_name="Temperatur", device_id=None, area_id=None, platform="mqtt", device_class="temperature", original_device_class=None, entity_category=None, disabled_by=None, hidden_by=None, config_entry_id="e2"),
            SimpleNamespace(entity_id="sensor.diag", name="Diagnose", original_name=None, device_id=None, area_id=None, platform="mqtt", device_class="signal_strength", original_device_class=None, entity_category="diagnostic", disabled_by=None, hidden_by=None, config_entry_id="e2"),
            SimpleNamespace(entity_id="number.unknown", name="Zahl", original_name=None, device_id=None, area_id=None, platform="mqtt", device_class=None, original_device_class=None, entity_category=None, disabled_by="user", hidden_by=None, config_entry_id="e2"),
        ]

    def test_registry_and_state_merge_area_fallback(self):
        devices = {"d1": SimpleNamespace(name="Flur Gerät", area_id="area1")}
        areas = {"area1": SimpleNamespace(name="Flur")}
        result = build_inventory({"entities": {e.entity_id: e for e in self.entities}}, {"devices": devices}, {"areas": areas}, {"light.flur_decke": SimpleNamespace(state="off", attributes={})})
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0].area_name, "Flur")
        self.assertIsNone(result[1].state)
        self.assertFalse(result[1].available)

    def test_device_and_area_views_are_deterministic_aggregates(self):
        entities = [
            {"entity_id": "light.a", "device_id": "d1", "device_name": "Lamp", "area_id": "a1", "area_name": "Living", "available": True, "compatibility": {"status": "supported"}, "homekit": {"configured_by_filter": True}, "integration_domain": "test"},
            {"entity_id": "sensor.b", "device_id": "d1", "device_name": "Lamp", "area_id": "a1", "area_name": "Living", "available": False, "compatibility": {"status": "unknown"}, "homekit": {"configured_by_filter": False}, "integration_domain": "test"},
            {"entity_id": "switch.c", "device_id": None, "area_id": None, "area_name": None, "available": True, "compatibility": {"status": "supported"}, "homekit": {"configured_by_filter": None}, "integration_domain": "mqtt"},
        ]
        devices = build_device_views(entities)
        areas = build_area_views(entities)
        self.assertEqual(devices[0]["entity_ids"], ["light.a", "sensor.b"])
        self.assertEqual(devices[0]["unavailable_count"], 1)
        self.assertEqual(areas[0]["name"], "Kein Bereich")
        self.assertEqual(areas[1]["device_count"], 1)

    def test_diagnostics_are_deterministic_and_read_only(self):
        inventory = [
            {"entity_id": "number.bad", "available": True, "compatibility": {"status": "unsupported", "reason": "unsupported"}, "homekit": {}},
            {"entity_id": "sensor.lost", "available": False, "compatibility": {"status": "supported"}, "homekit": {}},
        ]
        bridges = [{"entry_id": "b1", "filter": {"include_entities": ["number.bad", "sensor.missing"]}}]
        findings = build_diagnostics(inventory, bridges, {"valid": False, "error": "bad yaml"})
        self.assertEqual(findings, build_diagnostics(inventory, bridges, {"valid": False, "error": "bad yaml"}))
        self.assertEqual(diagnostics_summary(findings)["critical"], 2)
        self.assertTrue(any(item["code"] == "stale_filter_reference" for item in findings))

    def test_device_preview_is_explicitly_simulated(self):
        result = build_preview({"entity_id": "light.a", "name": "Lamp", "domain": "light", "state": "on", "attributes": {}, "compatibility": {"expected_type": "Lightbulb"}})
        self.assertTrue(result["simulation"])
        self.assertFalse(result["applied"])
        with self.assertRaises(ValueError):
            build_preview({"entity_id": "light.a", "compatibility": {}}, {"pairing_key": "secret"})

    def test_rules_are_deterministic_manual_first_and_conflict_safe(self):
        entities = [{"entity_id": "light.a", "area_name": "Living", "available": True, "compatibility": {"status": "supported"}}]
        rules = [
            {"id": "exclude", "priority": 5, "match": {"area_name": "Living"}, "action": "exclude"},
            {"id": "include", "priority": 10, "match": {"area_name": "Living"}, "action": "include"},
        ]
        result = evaluate_rules(entities, rules, {"light.a": "exclude"})
        self.assertEqual(result["decisions"][0]["source"], "manual")
        conflict = evaluate_rules(entities, rules)
        self.assertEqual(conflict["decisions"][0]["decision"], "unknown")
        self.assertEqual(len(conflict["conflicts"]), 1)
        self.assertFalse(conflict["applied"])

    def test_history_compare_and_restore_never_apply(self):
        before = {"schema_version": 1, "bridges": {"b": {"policy": "explicit_overrides", "entities": {"light.a": "include"}}}}
        after = {"schema_version": 1, "bridges": {"b": {"policy": "explicit_overrides", "entities": {"light.a": "exclude", "sensor.b": "include"}}}}
        diff = compare_history(before, after)
        self.assertEqual(diff["summary"]["changed"], 1)
        self.assertEqual(diff["summary"]["added"], 1)
        entry = make_history_entry(after)
        restored = restore_as_draft(entry)
        self.assertTrue(restored["restored"])
        self.assertFalse(restored["applied"])

    def test_performance_summary_is_deterministic(self):
        summary = summarize_inventory([
            {"entity_id": "light.a", "domain": "light", "available": True},
            {"entity_id": "sensor.b", "domain": "sensor", "available": False},
        ])
        self.assertEqual(summary["entity_count"], 2)
        self.assertEqual(summary["domain_counts"], {"light": 1, "sensor": 1})
        self.assertFalse(summary["virtualization_recommended"])

    def test_performance_summary_handles_release_scale_inventories(self):
        for count in (2500, 5000):
            entities = [
                {
                    "entity_id": f"light.synthetic_{index}",
                    "domain": "light",
                    "available": index % 10 != 0,
                }
                for index in range(count)
            ]
            summary = summarize_inventory(entities)
            self.assertEqual(summary["entity_count"], count)
            self.assertEqual(summary["unavailable_count"], count // 10)
            self.assertEqual(summary["domain_counts"], {"light": count})
            self.assertEqual(summary["recommended_page_size"], 100 if count == 2500 else 50)
            self.assertEqual(summary["virtualization_recommended"], count > 2500)

    def test_state_only_entities_are_visible_with_unknown_registry_metadata(self):
        result = build_inventory(
            {"entities": {}}, {}, {},
            {"sensor.runtime_only": SimpleNamespace(state="on", attributes={"friendly_name": "Runtime only"})},
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].entity_id, "sensor.runtime_only")
        self.assertEqual(result[0].name, "Runtime only")
        self.assertIsNone(result[0].integration_domain)
        self.assertTrue(result[0].available)

    def test_config_flow_uses_home_assistant_discovery_class_name(self):
        source = Path("custom_components/homekit_manager/config_flow.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        self.assertIn("ConfigFlow", classes)
        self.assertNotIn("HomeKitManagerConfigFlow", classes)
        methods = {node.name for node in classes["ConfigFlow"].body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertIn("async_step_user", methods)

    def test_compatibility_and_unknown_domains(self):
        self.assertEqual(classify_entity({"domain": "light"}).status, "supported")
        self.assertEqual(classify_entity({"domain": "sensor", "device_class": "temperature"}).expected_type, "TemperatureSensor")
        self.assertEqual(classify_entity({"domain": "number"}).status, "unknown")
        self.assertEqual(classify_entity({"domain": "binary_sensor"}).status, "conditionally_supported")

    def test_filter_precedence_and_default_exclusions(self):
        config = {"include_domains": ["light"], "exclude_entities": ["light.bad"], "include_entities": ["switch.explicit"]}
        self.assertEqual(evaluate_filter("switch.explicit", config=config).reason, "explicit_include")
        self.assertFalse(evaluate_filter("light.bad", config=config).configured)
        self.assertTrue(evaluate_filter("light.good", config=config).configured)
        self.assertFalse(evaluate_filter("sensor.diag", entity_category="diagnostic", config={}).configured)
        self.assertIsNone(evaluate_filter("light.x").configured)

    def test_filter_matches_core_category_and_explicit_include_semantics(self):
        core_filter = build_core_filter({})
        self.assertFalse(
            evaluate_filter(
                "sensor.diag",
                entity_category="diagnostic",
                config={},
                core_filter=core_filter,
            ).configured
        )
        explicit = build_core_filter({"include_entities": ["sensor.diag"]})
        self.assertTrue(
            evaluate_filter(
                "sensor.diag",
                entity_category="diagnostic",
                config={"include_entities": ["sensor.diag"]},
                core_filter=explicit,
            ).configured
        )

    def test_large_inventory(self):
        entries = {}
        states = {}
        for i in range(1500):
            entity_id = f"light.test_{i}"
            entries[entity_id] = SimpleNamespace(entity_id=entity_id, name=None, original_name=None, device_id=None, area_id=None, platform="test", device_class=None, original_device_class=None, entity_category=None, disabled_by=None, hidden_by=None, config_entry_id=None)
            states[entity_id] = SimpleNamespace(state="off", attributes={})
        self.assertEqual(len(build_inventory({"entities": entries}, {}, {}, states)), 1500)

    def test_draft_serialization_is_deterministic_and_non_persistent(self):
        result = serialize_draft("bridge-1", {"sensor.z": "exclude", "light.a": "include", "switch.x": "unchanged"})
        self.assertIn("light.a: include", result)
        self.assertIn("sensor.z: exclude", result)
        self.assertNotIn("switch.x", result)

    def test_yaml_store_missing_and_deterministic_atomic_save(self):
        with tempfile.TemporaryDirectory() as directory:
            store = YamlStore(Path(directory) / "homekit_manager.yaml")
            missing = store.load()
            self.assertFalse(missing.exists)
            document = {"schema_version": 1, "bridges": {"bridge-1": {"policy": "explicit_overrides", "entities": {"sensor.z": "exclude", "light.a": "include"}}}}
            saved = store.save(document, None)
            self.assertTrue(saved.valid)
            self.assertEqual(store.load().document["bridges"]["bridge-1"]["entities"], {"light.a": "include", "sensor.z": "exclude"})
            self.assertEqual(store.path.read_text(encoding="utf-8").count("schema_version: 1"), 1)

    def test_yaml_store_rejects_invalid_schema_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "homekit_manager.yaml"
            path.write_text("schema_version: 99\nbridges: {}\n", encoding="utf-8")
            store = YamlStore(path)
            snapshot = store.load()
            self.assertFalse(snapshot.valid)
            with self.assertRaises(YamlWriteError):
                store.save({"schema_version": 1, "bridges": {}}, snapshot.file_version)
            self.assertIn("schema_version: 99", path.read_text(encoding="utf-8"))

    def test_yaml_store_rejects_bad_entities_and_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            store = YamlStore(Path(directory) / "homekit_manager.yaml")
            with self.assertRaises(YamlValidationError):
                store.save({"schema_version": 1, "bridges": {"b": {"policy": "explicit_overrides", "entities": {"not an entity": "include"}}}}, None)
            first = store.save({"schema_version": 1, "bridges": {}}, None)
            with self.assertRaises(YamlVersionConflict):
                store.save({"schema_version": 1, "bridges": {}}, "stale")
            self.assertEqual(first.file_version, store.load().file_version)

    def test_yaml_store_concurrent_writers_use_optimistic_version(self):
        with tempfile.TemporaryDirectory() as directory:
            store = YamlStore(Path(directory) / "homekit_manager.yaml")
            initial = store.save({"schema_version": 1, "bridges": {}}, None)
            outcomes = []
            def write(entity_id):
                try:
                    store.save({"schema_version": 1, "bridges": {"b": {"policy": "explicit_overrides", "entities": {entity_id: "include"}}}}, initial.file_version)
                    outcomes.append("saved")
                except YamlVersionConflict:
                    outcomes.append("conflict")
            threads = [threading.Thread(target=write, args=(f"light.{letter}",)) for letter in ("a", "b")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(sorted(outcomes), ["conflict", "saved"])

    def test_yaml_store_atomic_replace_write_error(self):
        with tempfile.TemporaryDirectory() as directory:
            store = YamlStore(Path(directory) / "homekit_manager.yaml")
            with patch("custom_components.homekit_manager.yaml_store.os.replace", side_effect=OSError("disk full")):
                with self.assertRaises(YamlWriteError):
                    store.save({"schema_version": 1, "bridges": {}}, None)
            self.assertFalse(store.path.exists())

    def _planner_item(self, entity_id, configured, compatibility="supported", available=True):
        return {"entity_id": entity_id, "available": available, "compatibility": {"status": compatibility}, "homekit": {"configured_by_filter": configured}}

    def test_change_planner_include_exclude_and_unchanged(self):
        bridge = {"entry_id": "b", "filter": {"exclude_entities": ["light.off"]}}
        inventory = [self._planner_item("light.off", False), self._planner_item("light.on", True)]
        desired = {"schema_version": 1, "bridges": {"b": {"policy": "explicit_overrides", "entities": {"light.off": "include", "light.on": "exclude"}}}}
        result = plan_changes(bridge, desired, inventory)
        actions = {item["entity_id"]: item for item in result["changes"]}
        self.assertEqual(actions["light.off"]["action"], "add")
        self.assertEqual(actions["light.on"]["action"], "remove")
        self.assertTrue(result["summary"]["blocked"] is False)

    def test_change_planner_blocks_unknown_incompatible_removed_and_complex_filters(self):
        bridge = {"entry_id": "b", "filter": {"include_entity_globs": ["light.*"]}}
        inventory = [self._planner_item("sensor.unknown", None), self._planner_item("number.bad", False, "unsupported"), self._planner_item("light.off", True)]
        desired = {"schema_version": 1, "bridges": {"b": {"policy": "explicit_overrides", "entities": {"sensor.unknown": "include", "number.bad": "include", "switch.removed": "exclude", "light.off": "exclude"}}}}
        result = plan_changes(bridge, desired, inventory)
        actions = {item["entity_id"]: item for item in result["changes"]}
        self.assertEqual(actions["sensor.unknown"]["reason"], "unknown_current_filter")
        self.assertEqual(actions["number.bad"]["reason"], "incompatible_entity")
        self.assertEqual(actions["switch.removed"]["reason"], "entity_removed")
        self.assertEqual(actions["light.off"]["risk"], "high")
        self.assertTrue(result["summary"]["blocked"])

    def test_change_planner_large_inventory(self):
        inventory = [self._planner_item(f"light.test_{i}", True) for i in range(1500)]
        desired = {"schema_version": 1, "bridges": {"b": {"policy": "explicit_overrides", "entities": {"light.test_1499": "exclude"}}}}
        result = plan_changes({"entry_id": "b", "filter": {}}, desired, inventory)
        self.assertEqual(len(result["changes"]), 1500)
        self.assertEqual(result["summary"]["removed_includes"], 1)

    def test_options_diff_preserves_unrelated_options_and_filter_rules(self):
        bridge = {
            "entry_id": "b", "data": {"name": "Existing", "port": 21063, "filter": {"include_domains": ["light"], "exclude_entities": [], "include_entities": []}},
            "options": {"mode": "bridge", "filter": {"include_domains": ["light"], "exclude_entities": [], "include_entities": []}, "entity_config": {"light.a": {"type": "light"}}},
            "filter": {"include_domains": ["light"], "exclude_entities": [], "include_entities": []},
        }
        inventory = [self._planner_item("light.a", True), self._planner_item("light.b", True)]
        document = {"schema_version": 1, "bridges": {"b": {"policy": "explicit_overrides", "entities": {"light.a": "exclude"}}}}
        called = []
        diff = build_options_diff(bridge, document, inventory, core_options_validator=lambda options: called.append(options))
        self.assertEqual(diff.after["name"], "Existing")
        self.assertEqual(diff.after["port"], 21063)
        self.assertEqual(diff.after["entity_config"], {"light.a": {"type": "light"}})
        self.assertEqual(diff.after["filter"]["include_domains"], ["light"])
        self.assertEqual(diff.after["filter"]["exclude_entities"], ["light.a"])
        self.assertEqual(diff.after["filter"]["include_entities"], [])
        self.assertEqual(len(called), 1)

    def test_options_diff_blocks_unknown_and_writer_never_applies(self):
        bridge = {"entry_id": "b", "data": {}, "options": {}, "filter": None}
        document = {"schema_version": 1, "bridges": {"b": {"policy": "explicit_overrides", "entities": {"light.a": "include"}}}}
        with self.assertRaises(HomeKitWriteBlocked):
            build_options_diff(bridge, document, [self._planner_item("light.a", None)])
        calls = []
        fake_hass = SimpleNamespace(config_entries=SimpleNamespace(async_update_entry=lambda *args: calls.append(args)))
        with self.assertRaises(HomeKitWriteDisabled):
            asyncio.run(HomeKitWriter(fake_hass, test_environment=True).async_apply(SimpleNamespace()))
        self.assertEqual(calls, [])

    def test_reader_is_read_only_and_redacts_sensitive_values(self):
        entry = SimpleNamespace(
            entry_id="bridge-1", title="Test Bridge", source="user", state=SimpleNamespace(value="loaded"),
            supports_options=True, supports_reconfigure=False,
            data={"name": "Test", "port": 12345, "homekit_mode": "bridge", "filter": {"include_domains": ["light"]}, "password": "do-not-return"},
            options={"mode": "bridge", "entity_config": {"light.a": {"type": "light", "pairing_key": "do-not-return"}}, "token": "do-not-return"},
        )
        hass = SimpleNamespace(config_entries=SimpleNamespace(async_entries=lambda domain: [entry]))
        result = read_homekit_entries(hass)[0].as_dict()
        self.assertEqual(result["entry_id"], "bridge-1")
        self.assertEqual(result["mode"], "bridge")
        self.assertEqual(result["filter"], {"include_domains": ["light"]})
        self.assertNotIn("password", result["data"])
        self.assertNotIn("token", result["options"])
        self.assertNotIn("pairing_key", result["options"]["entity_config"]["light.a"])

    def test_reconcile_and_exports_never_claim_applied(self):
        document = {"schema_version": 1, "bridges": {"b": {"policy": "explicit_overrides", "entities": {"light.a": "include", "switch.b": "exclude"}}}}
        inventory = [self._planner_item("light.a", True), self._planner_item("switch.b", None)]
        result = reconcile_desired_state(document, "b", inventory, baseline_fingerprint="old", current_fingerprint="new")
        self.assertEqual(result["summary"]["satisfied"], 1)
        self.assertEqual(result["summary"]["unknown"], 1)
        self.assertEqual(result["apple_home_visible"], "unknown")
        self.assertIn("nicht angewendet", export_desired_state(document, "text"))
        self.assertIn('"schema_version": 1', export_desired_state(document, "json"))

if __name__ == "__main__":
    unittest.main()

