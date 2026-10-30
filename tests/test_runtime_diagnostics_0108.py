import unittest
import sys
from types import SimpleNamespace

# Load these value-only modules without executing the integration package's HA
# setup module. The full suite covers package imports in the HA test environment.
from pathlib import Path
package = "custom_components.homekit_manager"
if package not in sys.modules:
    module = type(sys)(package)
    module.__path__ = [str(Path(__file__).parents[1] / "custom_components" / "homekit_manager")]
    sys.modules[package] = module

from custom_components.homekit_manager.runtime_diagnostics import diagnose_runtime, runtime_publication_summary  # noqa: E402


class RuntimeDiagnostics0108Tests(unittest.TestCase):
    def inventory(self):
        return [
            {"entity_id": "light.living", "compatibility": {"status": "supported"}},
            {"entity_id": "sensor.temperature", "compatibility": {"status": "supported"}},
            {"entity_id": "sensor.internal", "compatibility": {"status": "unsupported"}},
        ]

    def accessory(self, entity_id, aid=1, with_services=True):
        services = {
            1: SimpleNamespace(
                service_type="public.hap.service.Lightbulb",
                display_name="Living light",
                iid=2,
                characteristics={
                    3: SimpleNamespace(characteristic_type="public.hap.characteristic.On", iid=3),
                },
            ),
        } if with_services else None
        return SimpleNamespace(entity_id=entity_id, display_name=entity_id, category=1, services=services, aid=aid)

    def entry(self, accessories, driver=True):
        homekit = SimpleNamespace(
            bridge=SimpleNamespace(accessories=accessories),
            driver=object() if driver else None,
        )
        return SimpleNamespace(entry_id="bridge-1", runtime_data=SimpleNamespace(homekit=homekit))

    def test_complete_mapping_is_value_free_and_counts_services(self):
        result = diagnose_runtime(
            SimpleNamespace(),
            self.entry({1: self.accessory("light.living"), 2: self.accessory("sensor.temperature", 2)}),
            self.inventory(),
        )
        self.assertEqual(result["completeness"], "verified")
        self.assertEqual(result["accessory_count"], 2)
        self.assertEqual(result["mapped_accessory_count"], 2)
        self.assertEqual(result["service_count"], 2)
        self.assertEqual(result["characteristic_count"], 2)
        self.assertEqual(result["entity_status"]["light.living"], "published_verified")
        self.assertEqual(result["entity_status"]["sensor.internal"], "unsupported")
        self.assertEqual(result["entity_status"]["sensor.internal"], "unsupported")
        self.assertNotIn("pairing", result)
        self.assertNotIn("private_key", result)
        self.assertNotIn("state", result["accessories"][0])
        self.assertEqual(len(result["accessories"][0]["accessory_id_fingerprint"]), 20)
        self.assertEqual(runtime_publication_summary(result)["entity_ids"], ["light.living", "sensor.temperature"])

    def test_ambiguous_runtime_is_partial_and_never_false_negative(self):
        result = diagnose_runtime(
            SimpleNamespace(),
            self.entry({1: self.accessory("light.living"), 2: self.accessory(None, 2)}),
            self.inventory(),
        )
        self.assertEqual(result["completeness"], "partial")
        self.assertEqual(result["entity_status"]["light.living"], "published_verified")
        self.assertEqual(result["entity_status"]["sensor.temperature"], "unknown")
        self.assertEqual(result["entity_status"]["sensor.internal"], "unsupported")
        self.assertEqual(result["ambiguous_accessory_count"], 1)
        self.assertEqual(runtime_publication_summary(result)["state"], "unknown")

    def test_missing_runtime_uses_unknown_for_every_supported_entity(self):
        entry = SimpleNamespace(entry_id="bridge-1", runtime_data=None)
        result = diagnose_runtime(SimpleNamespace(), entry, self.inventory())
        self.assertEqual(result["completeness"], "unknown")
        self.assertEqual(set(result["entity_status"].values()), {"unknown"})
        self.assertIsNone(result["accessory_count"])

    def test_missing_service_collection_does_not_claim_complete_characteristics(self):
        result = diagnose_runtime(
            SimpleNamespace(),
            self.entry({1: self.accessory("light.living", with_services=False)}),
            self.inventory(),
        )
        self.assertEqual(result["completeness"], "partial")
        self.assertIsNone(result["service_count"])
        self.assertIsNone(result["characteristic_count"])
        self.assertEqual(result["entity_status"]["light.living"], "published_verified")


if __name__ == "__main__":
    unittest.main()
