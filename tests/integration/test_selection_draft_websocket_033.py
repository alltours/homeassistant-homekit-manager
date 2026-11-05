"""Real Home Assistant WebSocket coverage for the non-mutating 0.10.33 flow."""
from __future__ import annotations

from copy import deepcopy

from pytest_homeassistant_custom_component.common import MockConfigEntry

# In the ZIP-install acceptance, import the integration explicitly so HA's
# custom-component loader discovers the extracted artifact rather than the
# source checkout.
import custom_components.homekit_manager  # noqa: F401
from custom_components.homekit_manager.fingerprint import build_fingerprint


async def _setup_selection_context(hass, enable_custom_integrations):
    native = MockConfigEntry(
        domain="homekit",
        entry_id="selection-bridge",
        title="Selection Bridge",
        source="user",
        data={"name": "Selection Bridge", "mode": "bridge"},
        options={"homekit_mode": "bridge", "filter": {"include_entities": ["light.keep"]}},
    )
    native.add_to_hass(hass)
    flow = await hass.config_entries.flow.async_init("homekit_manager", context={"source": "user"})
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    coordinator = hass.data["homekit_manager"]["coordinator"]
    coordinator.bridges = [{
        "entry_id": native.entry_id,
        "title": native.title,
        "filter": {"include_entities": ["light.keep"]},
    }]
    coordinator.selected_bridge_id = native.entry_id
    coordinator.inventory = [{
        "entity_id": "light.keep",
        "name": "Keep light",
        "domain": "light",
        "device_name": "Test device",
        "area_name": "Test area",
        "integration_domain": "test",
        "availability_status": "available",
        "homekit": {"configured_by_filter": True, "current_status": "included"},
        "unique_id": "light-keep",
        "device_id": "device-keep",
        "config_entry_id": "test-entry",
    }]
    coordinator.runtime_diagnosis = {
        "completeness": "complete",
        "ambiguous_accessory_count": 0,
        "entity_status": {"light.keep": "published_verified"},
    }
    coordinator.snapshot_revision = 7
    coordinator.snapshot_timestamp = "2026-11-03T00:00:00+00:00"
    coordinator.snapshot_complete = True
    coordinator.fingerprint = "selection-fingerprint-7"
    coordinator.selection_reconciliation = {
        "state": "aligned",
        "selection_conflict": False,
    }
    return native, coordinator


async def test_selection_websocket_round_trip_and_persistence_is_non_mutating(
    hass, enable_custom_integrations, hass_ws_client,
):
    native, coordinator = await _setup_selection_context(hass, enable_custom_integrations)
    before_options = deepcopy(dict(native.options))
    client = await hass_ws_client()

    await client.send_json_auto_id({"type": "homekit_manager/selection_draft"})
    initial = await client.receive_json()
    assert initial["success"] is True
    model = initial["result"]
    assert model["snapshot"]["bridge_entry_id"] == native.entry_id
    assert model["entities"][0]["user_decision"] == "REVIEW"
    assert model["plan"]["apply_allowed"] is False

    draft = deepcopy(model["draft"])
    draft["decisions"]["light.keep"] = {
        "decision": "KEEP",
        "identity": model["entities"][0]["identity"],
    }
    # Simulate a coordinator refresh that only advanced the revision; the
    # semantic fingerprint is unchanged and must keep this non-mutating draft
    # usable while normalization binds it to the current revision.
    draft["snapshot_revision"] = 6
    await client.send_json_auto_id({
        "type": "homekit_manager/save_selection_draft",
        "draft": draft,
        "expected_revision": 6,
        "expected_fingerprint": "selection-fingerprint-7",
    })
    saved = await client.receive_json()
    assert saved["success"] is True, saved
    assert saved["result"]["draft"]["decisions"]["light.keep"]["decision"] == "KEEP"
    assert saved["result"]["draft"]["snapshot_revision"] == 7
    assert saved["result"]["plan"]["native_mutation_performed"] is False
    assert saved["result"]["plan"]["apply_allowed"] is False

    await client.send_json_auto_id({"type": "homekit_manager/selection_plan"})
    planned = await client.receive_json()
    assert planned["success"] is True
    assert planned["result"]["hypothetical_target_includes"] == ["light.keep"]
    assert planned["result"]["native_mutation_performed"] is False

    reloaded_store = await coordinator.selection_draft_store.async_load()
    assert reloaded_store[native.entry_id]["decisions"]["light.keep"]["decision"] == "KEEP"
    assert dict(native.options) == before_options


async def test_selection_websocket_rejects_unknown_and_unexpected_data(
    hass, enable_custom_integrations, hass_ws_client,
):
    native, _coordinator = await _setup_selection_context(hass, enable_custom_integrations)
    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "homekit_manager/selection_draft"})
    model = (await client.receive_json())["result"]

    unknown = deepcopy(model["draft"])
    unknown["decisions"]["light.unknown"] = {"decision": "KEEP"}
    await client.send_json_auto_id({"type": "homekit_manager/save_selection_draft", "draft": unknown})
    rejected_unknown = await client.receive_json()
    assert rejected_unknown["success"] is False
    assert rejected_unknown["error"]["code"] == "invalid_decision_draft"

    unexpected = deepcopy(model["draft"])
    unexpected["unexpected"] = True
    await client.send_json_auto_id({"type": "homekit_manager/save_selection_draft", "draft": unexpected})
    rejected_unexpected = await client.receive_json()
    assert rejected_unexpected["success"] is False
    assert rejected_unexpected["error"]["code"] == "invalid_decision_draft"

    foreign = deepcopy(model["draft"])
    foreign["bridge_entry_id"] = "another-bridge"
    await client.send_json_auto_id({"type": "homekit_manager/selection_plan", "draft": foreign})
    rejected_foreign = await client.receive_json()
    assert rejected_foreign["success"] is False
    assert rejected_foreign["error"]["code"] == "plan_blocked"
    assert dict(native.options) == {"homekit_mode": "bridge", "filter": {"include_entities": ["light.keep"]}}


async def test_saved_selection_draft_can_be_discarded_and_alignment_is_read_only(
    hass, enable_custom_integrations, hass_ws_client,
):
    native, coordinator = await _setup_selection_context(hass, enable_custom_integrations)
    before_options = deepcopy(dict(native.options))
    client = await hass_ws_client()

    await client.send_json_auto_id({"type": "homekit_manager/selection_draft"})
    model = (await client.receive_json())["result"]
    draft = deepcopy(model["draft"])
    draft["decisions"]["light.keep"] = {"decision": "KEEP", "identity": model["entities"][0]["identity"]}
    await client.send_json_auto_id({
        "type": "homekit_manager/save_selection_draft",
        "draft": draft,
        "expected_fingerprint": model["snapshot"]["snapshot_fingerprint"],
        "expected_revision": model["snapshot"]["snapshot_revision"],
    })
    saved = (await client.receive_json())["result"]
    assert saved["draft_fingerprint"]

    await client.send_json_auto_id({"type": "homekit_manager/selection_alignment"})
    alignment = (await client.receive_json())["result"]
    assert alignment["native_mutation_performed"] is False
    assert alignment["manager_metadata_mutation_performed"] is False
    assert alignment["native_include_entities"] == ["light.keep"]

    await client.send_json_auto_id({
        "type": "homekit_manager/discard_selection_draft",
        "entry_id": native.entry_id,
        "expected_draft_fingerprint": saved["draft_fingerprint"],
    })
    discarded = (await client.receive_json())["result"]
    assert discarded["draft_fingerprint"] is None
    assert native.entry_id not in await coordinator.selection_draft_store.async_load()
    assert dict(native.options) == before_options


async def test_discard_selection_draft_is_bridge_bound(
    hass, enable_custom_integrations, hass_ws_client,
):
    _native, _coordinator = await _setup_selection_context(hass, enable_custom_integrations)
    client = await hass_ws_client()
    await client.send_json_auto_id({
        "type": "homekit_manager/discard_selection_draft",
        "entry_id": "foreign-bridge",
    })
    response = await client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "conflict"


async def test_confirmed_alignment_adopts_native_metadata_without_homekit_mutation(
    hass, enable_custom_integrations, hass_ws_client,
):
    native, coordinator = await _setup_selection_context(hass, enable_custom_integrations)
    before_options = deepcopy(dict(native.options))
    client = await hass_ws_client()

    await client.send_json_auto_id({"type": "homekit_manager/selection_alignment"})
    preview = (await client.receive_json())["result"]
    assert preview["native_without_manager_metadata"] == ["light.keep"]
    assert preview["manager_metadata_mutation_performed"] is False

    await client.send_json_auto_id({
        "type": "homekit_manager/selection_alignment_apply",
        "entry_id": native.entry_id,
        "expected_snapshot_fingerprint": preview["snapshot_fingerprint"],
        "expected_snapshot_revision": preview["snapshot_revision"],
        "expected_manager_document_fingerprint": preview["manager_document_fingerprint"],
        "expected_manager_file_version": preview["manager_file_version"],
        "adopt_native_entities": ["light.keep"],
        "remove_stale_entities": [],
        "confirmed": True,
    })
    applied = await client.receive_json()
    assert applied["success"] is True, applied
    result = applied["result"]
    assert result["native_mutation_performed"] is False
    assert result["manager_metadata_mutation_performed"] is True
    assert result["changed_entities"] == {"adopted_native": ["light.keep"], "removed_stale": []}
    assert result["native_without_manager_metadata"] == []
    assert dict(native.options) == before_options

    stored = await hass.async_add_executor_job(coordinator.yaml_store.load)
    assert stored.document["bridges"][native.entry_id]["entities"] == {"light.keep": "include"}
    assert {item["reason"] for item in coordinator.history_entries} >= {"alignment_before_change", "alignment_metadata_confirmed"}

    await client.send_json_auto_id({
        "type": "homekit_manager/selection_alignment_apply",
        "entry_id": native.entry_id,
        "expected_snapshot_fingerprint": preview["snapshot_fingerprint"],
        "expected_snapshot_revision": preview["snapshot_revision"],
        "expected_manager_document_fingerprint": preview["manager_document_fingerprint"],
        "expected_manager_file_version": preview["manager_file_version"],
        "adopt_native_entities": ["light.keep"],
        "remove_stale_entities": [],
        "confirmed": True,
    })
    conflict = await client.receive_json()
    assert conflict["success"] is False
    assert conflict["error"]["code"] in {"conflict", "metadata_conflict"}
    assert dict(native.options) == before_options


async def test_alignment_requires_explicit_confirmation_and_valid_candidates(
    hass, enable_custom_integrations, hass_ws_client,
):
    native, _coordinator = await _setup_selection_context(hass, enable_custom_integrations)
    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "homekit_manager/selection_alignment"})
    preview = (await client.receive_json())["result"]

    payload = {
        "type": "homekit_manager/selection_alignment_apply",
        "entry_id": native.entry_id,
        "expected_snapshot_fingerprint": preview["snapshot_fingerprint"],
        "expected_snapshot_revision": preview["snapshot_revision"],
        "expected_manager_document_fingerprint": preview["manager_document_fingerprint"],
        "expected_manager_file_version": preview["manager_file_version"],
        "adopt_native_entities": ["light.keep"],
        "remove_stale_entities": [],
        "confirmed": False,
    }
    await client.send_json_auto_id(payload)
    rejected = await client.receive_json()
    assert rejected["success"] is False
    assert rejected["error"]["code"] == "metadata_alignment_blocked"

    await client.send_json_auto_id(payload | {"confirmed": True, "adopt_native_entities": ["light.unknown"]})
    invalid = await client.receive_json()
    assert invalid["success"] is False
    assert invalid["error"]["code"] == "metadata_alignment_blocked"


async def test_confirmed_alignment_removes_only_stale_manager_metadata(
    hass, enable_custom_integrations, hass_ws_client,
):
    native, coordinator = await _setup_selection_context(hass, enable_custom_integrations)
    before_options = deepcopy(dict(native.options))
    document = {"schema_version": 1, "bridges": {
        native.entry_id: {"policy": "explicit_overrides", "entities": {"sensor.old": "exclude"}},
    }}
    saved = await hass.async_add_executor_job(coordinator.yaml_store.save, document, None)
    coordinator.yaml_snapshot = saved
    coordinator.fingerprint = build_fingerprint(coordinator.bridges, coordinator.inventory, saved.document)
    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "homekit_manager/selection_alignment"})
    preview = (await client.receive_json())["result"]
    assert [item["entity_id"] for item in preview["stale_manager_entities"]] == ["sensor.old"]

    await client.send_json_auto_id({
        "type": "homekit_manager/selection_alignment_apply",
        "entry_id": native.entry_id,
        "expected_snapshot_fingerprint": preview["snapshot_fingerprint"],
        "expected_snapshot_revision": preview["snapshot_revision"],
        "expected_manager_document_fingerprint": preview["manager_document_fingerprint"],
        "expected_manager_file_version": preview["manager_file_version"],
        "adopt_native_entities": [],
        "remove_stale_entities": ["sensor.old"],
        "confirmed": True,
    })
    response = await client.receive_json()
    assert response["success"] is True, response
    result = response["result"]
    assert result["native_mutation_performed"] is False
    assert result["changed_entities"] == {"adopted_native": [], "removed_stale": ["sensor.old"]}
    current = await hass.async_add_executor_job(coordinator.yaml_store.load)
    assert current.document["bridges"][native.entry_id]["entities"] == {}
    assert dict(native.options) == before_options
