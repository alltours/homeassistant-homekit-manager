"""Regression coverage for 0.10.10 reconciliation and hidden entities."""
from __future__ import annotations

import unittest
import sys
from pathlib import Path

package = "custom_components.homekit_manager"
if package not in sys.modules:
    module = type(sys)(package)
    module.__path__ = [str(Path(__file__).parents[1] / "custom_components" / "homekit_manager")]
    sys.modules[package] = module

from custom_components.homekit_manager.bulk import preview_bulk  # noqa: E402
from custom_components.homekit_manager.change_planner import plan_changes  # noqa: E402
from custom_components.homekit_manager.selection_reconciliation import reconcile_selection  # noqa: E402


def entity(
    entity_id: str,
    *,
    configured: bool = True,
    reason: str = "domain_include",
    hidden: str | None = None,
    disabled: str | None = None,
    category: str | None = None,
    compatibility: str = "supported",
    device_id: str | None = "device-1",
    area_id: str | None = "area-1",
) -> dict:
    return {
        "entity_id": entity_id,
        "device_id": device_id,
        "device_registry_status": "main" if device_id else "none",
        "area_id": area_id,
        "registry_entry_present": True,
        "state_present": True,
        "hidden_by": hidden,
        "disabled_by": disabled,
        "device_disabled_by": None,
        "entity_category": category,
        "available": True,
        "compatibility": {"status": compatibility},
        "homekit": {"configured_by_filter": configured, "filter_reason": reason},
    }


class SelectionReconciliation01010Tests(unittest.TestCase):
    def test_legacy_54_excludes_plus_6_native_explicit_includes_are_60_rows(self):
        excludes = {f"sensor.excluded_{index}" for index in range(54)}
        inventory = [
            entity(entity_id, configured=True)
            for entity_id in sorted(excludes)
        ] + [
            entity(f"light.explicit_{index}", reason="explicit_include")
            for index in range(6)
        ]
        document = {"bridges": {"bridge": {"policy": "explicit_overrides", "entities": {
            entity_id: "exclude" for entity_id in sorted(excludes)
        }}}}

        result = reconcile_selection(document, "bridge", inventory, {
            "include_domains": ["sensor"],
            "include_entities": [f"light.explicit_{index}" for index in range(6)],
        })

        self.assertEqual(result["differences"]["count"], 60)
        self.assertEqual(result["scope"], "manager_native_runtime_selection")
        self.assertEqual(result["deviation_count"], 60)
        self.assertEqual(result["deviation_summary"], {
            "manager_exclude_native": 54,
            "native_explicit_unmanaged": 6,
        })
        self.assertEqual(len(result["deviations"]), 60)
        self.assertEqual(len({row["id"] for row in result["deviations"]}), 60)

    def test_stale_and_invalid_manager_entries_are_explicit_rows(self):
        result = reconcile_selection(
            {"bridges": {"bridge": {"policy": "explicit_overrides", "entities": {
                "sensor.gone": "exclude",
                "sensor.invalid": "maybe",
            }}}},
            "bridge",
            [entity("light.present", configured=True)],
            {"include_domains": ["light"]},
        )
        self.assertEqual(result["differences"]["count"], 2)
        self.assertEqual(result["deviation_count"], 2)
        self.assertEqual(result["manager"]["stale_decisions"], ["sensor.gone"])
        self.assertEqual(result["manager"]["invalid_decisions"], ["sensor.invalid"])

    def test_deviation_rows_include_entity_and_runtime_evidence(self):
        inventory = [entity("light.present", configured=True, reason="explicit_include")]
        inventory[0]["name"] = "Ceiling"
        inventory[0]["device_id"] = "device-1"
        inventory[0]["device_name"] = "Lamp"
        inventory[0]["area_id"] = "area-1"
        inventory[0]["area_name"] = "Hall"
        inventory[0]["domain"] = "light"
        inventory[0]["homekit"]["runtime_publication"] = "published_verified"
        result = reconcile_selection(
            {"bridges": {"bridge": {"policy": "explicit_overrides", "entities": {}}}},
            "bridge",
            inventory,
            {"include_entities": ["light.present"]},
            {
                "state": "verified",
                "entity_status": {"light.present": "published_verified"},
                "accessories": [{"entity_id": "light.present", "aid": 7, "iid_signature": "iid"}],
            },
            {"completeness": "verified", "entity_status": {"light.present": "published_verified"}},
        )
        self.assertEqual(result["deviation_count"], 1)
        row = result["deviations"][0]
        self.assertEqual(row["classification"], "native_explicit_unmanaged")
        self.assertEqual(row["device_name"], "Lamp")
        self.assertEqual(row["area_name"], "Hall")
        self.assertTrue(row["native_selection"])
        self.assertIsNone(row["manager_decision"])
        self.assertEqual(row["runtime_selection"], "published_verified")
        self.assertEqual(row["aid"], 7)
        self.assertEqual(row["verification_status"], "VERIFIED")

    def test_hidden_entity_requires_explicit_selection_but_not_bulk_scope(self):
        hidden = entity("light.hidden", hidden="user")
        hidden["homekit"]["registry_eligible"] = False
        area = preview_bulk([hidden], "area", "area:area-1")
        selection = preview_bulk([hidden], "selection", "", entity_ids=["light.hidden"])
        self.assertEqual(area["eligible_entity_ids"], [])
        self.assertEqual(area["skipped"], {"hidden": 1})
        self.assertEqual(selection["eligible_entity_ids"], ["light.hidden"])

    def test_hidden_explicit_include_is_plannable_but_disabled_is_not(self):
        hidden = entity("light.hidden", configured=False, hidden="user")
        hidden["homekit"]["registry_eligible"] = False
        result = plan_changes(
            {"entry_id": "bridge", "filter": {"include_domains": ["light"]}},
            {"schema_version": 1, "bridges": {"bridge": {"policy": "positive_list", "entities": {"light.hidden": "include"}}}},
            [hidden],
            "bridge",
        )
        self.assertFalse(result["summary"]["blocked"])
        self.assertEqual(result["changes"][0]["reason"], "explicit_include")

        disabled = entity("light.disabled", configured=False, hidden="user", disabled="user")
        blocked = plan_changes(
            {"entry_id": "bridge", "filter": {"include_domains": ["light"]}},
            {"schema_version": 1, "bridges": {"bridge": {"policy": "positive_list", "entities": {"light.disabled": "include"}}}},
            [disabled],
            "bridge",
        )
        self.assertTrue(blocked["summary"]["blocked"])
        self.assertEqual(blocked["changes"][0]["reason"], "disabled")

    def test_eight_hidden_matter_lamps_are_explicit_and_group_is_removed(self):
        lamps = [f"light.flur_flur_decke_{index}" for index in range(1, 9)]
        inventory = [
            entity(entity_id, configured=False, hidden="user")
            for entity_id in lamps
        ] + [entity("light.flur_decke", configured=True)]
        document = {
            "schema_version": 1,
            "bridges": {"bridge": {"policy": "positive_list", "entities": {
                entity_id: "include" for entity_id in lamps
            }}},
        }
        result = plan_changes(
            {"entry_id": "bridge", "filter": {"include_domains": ["light"]}},
            document,
            inventory,
            "bridge",
        )
        self.assertFalse(result["summary"]["blocked"])
        self.assertEqual(
            {change["entity_id"] for change in result["changes"] if change["action"] == "add"},
            set(lamps),
        )
        self.assertEqual(
            [change["action"] for change in result["changes"] if change["entity_id"] == "light.flur_decke"],
            ["remove"],
        )


if __name__ == "__main__":
    unittest.main()
