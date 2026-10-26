"""Home Assistant Core integration tests for the HomeKit Manager."""

import pytest

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant import loader
from homeassistant.components import websocket_api
from homeassistant.components import frontend
from homeassistant.helpers import area_registry, device_registry, entity_registry

from custom_components.homekit_manager.homekit_writer import (
    HomeKitWriteDisabled,
    HomeKitWriter,
    OptionsDiff,
)


async def test_homekit_manager_discovery_and_registration(
    hass, enable_custom_integrations
):
    """Tests A/B: discovery finds the domain and registration creates a handler."""
    integrations = await loader.async_get_custom_components(hass)
    assert "homekit_manager" in integrations

    result = await hass.config_entries.flow.async_init(
        "homekit_manager",
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == "form"
    assert result["handler"] == "homekit_manager"
    assert result["step_id"] == "user"


async def test_homekit_manager_user_flow_and_setup(hass, enable_custom_integrations):
    """Tests C/D/E/G: user flow, entry creation, setup, and regression."""
    result = await hass.config_entries.flow.async_init(
        "homekit_manager",
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == "form"
    assert result["handler"] == "homekit_manager"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "HomeKit Manager"
    entry = hass.config_entries.async_entries("homekit_manager")[0]
    # In Core 2026.10.4, async_configure() sets up a newly created entry before
    # returning the create_entry result. A second async_setup() is forbidden.
    assert entry.state is ConfigEntryState.LOADED
    await hass.async_block_till_done()


async def test_homekit_manager_writer_stays_disabled(hass, enable_custom_integrations):
    """Test F: the production HomeKit writer rejects application."""
    writer = HomeKitWriter(hass)
    with pytest.raises(HomeKitWriteDisabled):
        await writer.async_apply(None)


async def test_isolated_core_options_adapter_updates_real_config_entries(hass, monkeypatch):
    """The gated adapter exercises HA's real ConfigEntries update mechanism."""
    async def no_network_start(_self):
        return None

    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain="homekit",
        title="Isolated Test Bridge",
        data={"name": "Isolated Test Bridge", "port": 21063},
        options={"filter": {"include_entities": ["light.before"]}},
        source=config_entries.SOURCE_USER,
        entry_id="isolated-homekit-entry",
        unique_id=None,
        discovery_keys={},
        subentries_data=None,
    )
    await hass.config_entries.async_add(entry)
    diff = OptionsDiff(
        entry.entry_id,
        {"filter": {"include_entities": ["light.before"]}},
        {"filter": {"include_entities": ["light.before", "light.after"]}},
        ("filter",),
        ("light.after",),
        {"summary": {"blocked": False}},
    )
    result = await HomeKitWriter(hass, test_environment=True, apply_enabled=True).async_apply(diff)
    assert result["applied"] is True
    assert hass.config_entries.async_get_entry(entry.entry_id).options["filter"]["include_entities"] == ["light.before", "light.after"]


async def test_homekit_manager_entry_lifecycle(hass, enable_custom_integrations):
    """Setup and unload use the HA config-entry lifecycle without side effects."""
    result = await hass.config_entries.flow.async_init(
        "homekit_manager",
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    entry = hass.config_entries.async_entries("homekit_manager")[0]
    assert result["type"] == "create_entry"
    assert entry.state is ConfigEntryState.LOADED
    assert "homekit_manager" in hass.data
    assert frontend.async_panel_exists(hass, "homekit_manager")
    panel = hass.data[frontend.DATA_PANELS]["homekit_manager"]
    assert panel.config["_panel_custom"]["name"] == "homekit-manager-panel"

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert "homekit_manager" not in hass.data
    assert not frontend.async_panel_exists(hass, "homekit_manager")


async def test_homekit_manager_websocket_registration(hass, enable_custom_integrations):
    """All manager commands are registered in the real HA WebSocket registry."""
    result = await hass.config_entries.flow.async_init(
        "homekit_manager",
        context={"source": config_entries.SOURCE_USER},
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    commands = hass.data[websocket_api.DOMAIN]
    expected = {
        "homekit_manager/inventory",
        "homekit_manager/bridges",
        "homekit_manager/select_bridge",
        "homekit_manager/mode_status",
        "homekit_manager/set_mode",
        "homekit_manager/devices",
        "homekit_manager/areas",
        "homekit_manager/diagnostics",
        "homekit_manager/device_preview",
        "homekit_manager/rules_preview",
        "homekit_manager/history",
        "homekit_manager/history_restore",
        "homekit_manager/performance",
        "homekit_manager/yaml_status",
        "homekit_manager/validate_draft",
        "homekit_manager/preview",
        "homekit_manager/save_draft",
        "homekit_manager/apply_options_diff",
        "homekit_manager/prepare_options_diff",
        "homekit_manager/reconcile",
        "homekit_manager/export",
    }
    assert expected.issubset(commands)


async def test_homekit_manager_is_singleton(hass, enable_custom_integrations):
    """The central manager must not create a second config entry."""
    first = await hass.config_entries.flow.async_init(
        "homekit_manager", context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(first["flow_id"], {})
    second = await hass.config_entries.flow.async_init(
        "homekit_manager", context={"source": config_entries.SOURCE_USER}
    )
    assert second["type"] == "abort"
    assert second["reason"] == "already_configured"


async def test_homekit_manager_reads_real_registries(hass, enable_custom_integrations):
    """The coordinator reads live HA registries and state values."""
    result = await hass.config_entries.flow.async_init(
        "homekit_manager", context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    manager_entry = hass.config_entries.async_entries("homekit_manager")[0]
    device = device_registry.async_get(hass).async_get_or_create(
        config_entry_id=manager_entry.entry_id,
        identifiers={("test", "device-1")},
        name="Test Device",
    )
    area = area_registry.async_get(hass).async_get_or_create("Test Area")
    entity = entity_registry.async_get(hass).async_get_or_create(
        "light", "test", "light-1", suggested_object_id="test_light", device_id=device.id,
        original_name="Test Light",
    )
    entity_registry.async_get(hass).async_update_entity(entity.entity_id, area_id=area.id)
    hass.states.async_set(entity.entity_id, "on", {"friendly_name": "Test Light"})
    await hass.async_block_till_done()

    coordinator = hass.data["homekit_manager"]["coordinator"]
    await coordinator.async_refresh()
    record = next(item for item in coordinator.inventory if item["entity_id"] == entity.entity_id)
    assert record["area_name"] == "Test Area"
    assert record["device_name"] == "Test Device"
    assert record["available"] is True
    assert record["homekit"]["current_status"] in {"included", "excluded", "unknown"}
    assert coordinator.overview()["active_entities"] >= 1


async def test_homekit_manager_inventory_websocket_round_trip(
    hass, enable_custom_integrations, hass_ws_client
):
    """An authenticated administrator can read the inventory through HA WebSocket."""
    result = await hass.config_entries.flow.async_init(
        "homekit_manager", context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "homekit_manager/inventory"})
    response = await client.receive_json()
    assert response["type"] == "result"
    assert response["success"] is True
    assert "overview" in response["result"]
    assert "entities" in response["result"]


async def test_homekit_manager_apply_uses_authenticated_websocket(
    hass, enable_custom_integrations, hass_ws_client, monkeypatch
):
    """The real HA WebSocket transport reaches the guarded SOURCE_USER writer."""
    async def no_network_start(_self):
        return None

    monkeypatch.setattr("homeassistant.components.homekit.HomeKit.async_start", no_network_start)
    monkeypatch.setattr("homeassistant.components.homekit.async_port_is_available", lambda _port: True)
    bridge = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain="homekit",
        title="Authenticated WebSocket Bridge",
        data={"name": "Authenticated WebSocket Bridge", "port": 21064},
        options={"filter": {"include_entities": []}},
        source=config_entries.SOURCE_USER,
        entry_id="authenticated-ws-bridge",
        unique_id=None,
        discovery_keys={},
        subentries_data=None,
    )
    await hass.config_entries.async_add(bridge)
    flow = await hass.config_entries.flow.async_init(
        "homekit_manager", context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    coordinator = hass.data["homekit_manager"]["coordinator"]
    await coordinator.async_refresh()
    coordinator.inventory = [{
        "entity_id": "input_boolean.test_a",
        "entity_category": None,
        "hidden_by": None,
        "compatibility": {"status": "supported"},
        "homekit": {"configured_by_filter": False, "current_status": "excluded"},
    }]
    client = await hass_ws_client()
    document = {
        "schema_version": 1,
        "bridges": {
            bridge.entry_id: {
                "policy": "explicit_overrides",
                "entities": {"input_boolean.test_a": "include"},
            }
        },
    }
    await client.send_json_auto_id({
        "type": "homekit_manager/apply_options_diff",
        "document": document,
    })
    response = await client.receive_json()
    assert response["type"] == "result"
    assert response["success"] is True
    assert response["result"]["applied"] is True
    assert "input_boolean.test_a" in hass.config_entries.async_get_entry(bridge.entry_id).options["filter"]["include_entities"]
    await client.send_json_auto_id({
        "type": "homekit_manager/activation_status",
        "entry_id": bridge.entry_id,
        "request_id": response["result"]["request_id"],
    })
    status_response = await client.receive_json()
    assert status_response["success"] is True
    assert status_response["result"]["state"] == "active"


async def test_homekit_manager_duplicate_request_id_does_not_retry_failed_apply(
    hass, enable_custom_integrations, monkeypatch
):
    """A failed request ID is terminal and cannot trigger an implicit retry."""
    result = await hass.config_entries.flow.async_init(
        "homekit_manager", context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    coordinator = hass.data["homekit_manager"]["coordinator"]
    coordinator.bridges = [{"entry_id": "bridge-a", "source": "user", "filter": {}}]
    coordinator.selected_bridge_id = "bridge-a"
    coordinator.inventory = [{
        "entity_id": "light.test",
        "compatibility": {"status": "supported"},
        "homekit": {"configured_by_filter": False, "current_status": "excluded"},
    }]
    coordinator.fingerprint = "fingerprint"

    class FailingWriter:
        calls = 0

        async def async_apply(self, _diff):
            self.calls += 1
            raise RuntimeError("reload failed")

    writer = FailingWriter()
    monkeypatch.setattr("custom_components.homekit_manager.coordinator.HomeKitWriter", lambda *_args, **_kwargs: writer)
    document = {"schema_version": 1, "bridges": {"bridge-a": {"policy": "explicit_overrides", "entities": {"light.test": "include"}}}}

    with pytest.raises(RuntimeError, match="reload failed"):
        await coordinator.async_apply_options_diff(document, "fingerprint", "request-1")
    result = await coordinator.async_apply_options_diff(document, "fingerprint", "request-1")

    assert result["activation_status"] == "failed"
    assert result["applied"] is False
    assert writer.calls == 1


async def test_homekit_manager_mode_status_is_conservative(
    hass, enable_custom_integrations, hass_ws_client
):
    """Mode reporting never claims that a bridge migration was applied."""
    result = await hass.config_entries.flow.async_init(
        "homekit_manager", context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "homekit_manager/mode_status"})
    response = await client.receive_json()
    assert response["success"] is True
    status = response["result"]
    assert status["active_mode"] in {"yaml", "homekit_bridge", "homekit_manager"}
    assert status["transition"] == "stable"
    assert all(item["status"] in {"safe", "manual_required"} for item in status["matrix"].values())
    for direction in (
        "yaml->homekit_bridge", "homekit_bridge->yaml",
        "homekit_bridge->homekit_manager", "homekit_manager->homekit_bridge",
        "yaml->homekit_manager", "homekit_manager->yaml",
    ):
        assert status["matrix"][direction]["status"] == "manual_required"


async def test_homekit_manager_devices_and_areas_websocket_round_trip(
    hass, enable_custom_integrations, hass_ws_client
):
    """Device and area views are read-only aggregates of the live registries."""
    result = await hass.config_entries.flow.async_init(
        "homekit_manager", context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    client = await hass_ws_client()
    for command, key in (("homekit_manager/devices", "devices"), ("homekit_manager/areas", "areas")):
        await client.send_json_auto_id({"type": command})
        response = await client.receive_json()
        assert response["type"] == "result"
        assert response["success"] is True
        assert key in response["result"]


async def test_homekit_manager_diagnostics_websocket_round_trip(
    hass, enable_custom_integrations, hass_ws_client
):
    """Diagnostics are exposed as findings and never perform corrections."""
    result = await hass.config_entries.flow.async_init(
        "homekit_manager", context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "homekit_manager/diagnostics"})
    response = await client.receive_json()
    assert response["success"] is True
    assert "findings" in response["result"]
    assert "summary" in response["result"]


async def test_homekit_manager_device_preview_is_simulated(
    hass, enable_custom_integrations, hass_ws_client
):
    """Device preview never reports an applied HomeKit change."""
    result = await hass.config_entries.flow.async_init(
        "homekit_manager", context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    coordinator = hass.data["homekit_manager"]["coordinator"]
    coordinator.inventory = [{"entity_id": "light.test", "name": "Test", "domain": "light", "compatibility": {"expected_type": "Lightbulb"}, "attributes": {}, "state": "on"}]
    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "homekit_manager/device_preview", "entity_id": "light.test"})
    response = await client.receive_json()
    assert response["success"] is True
    assert response["result"]["simulation"] is True
    assert response["result"]["applied"] is False


async def test_homekit_manager_rules_preview_is_suggestion_only(
    hass, enable_custom_integrations, hass_ws_client
):
    """Rules are evaluated but never persisted or applied."""
    result = await hass.config_entries.flow.async_init(
        "homekit_manager", context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    coordinator = hass.data["homekit_manager"]["coordinator"]
    coordinator.inventory = [{"entity_id": "light.test", "domain": "light", "area_name": "Living", "available": True, "compatibility": {"status": "supported"}}]
    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "homekit_manager/rules_preview", "rules": [{"id": "living-lights", "priority": 10, "match": {"area_name": "Living"}, "action": "include"}]})
    response = await client.receive_json()
    assert response["success"] is True
    assert response["result"]["decisions"][0]["decision"] == "include"
    assert response["result"]["applied"] is False


async def test_homekit_manager_history_is_read_only_and_restorable_as_draft(
    hass, enable_custom_integrations, hass_ws_client
):
    """History restoration returns a draft and never an active configuration."""
    result = await hass.config_entries.flow.async_init(
        "homekit_manager", context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    coordinator = hass.data["homekit_manager"]["coordinator"]
    coordinator.history_entries = [{"document": {"schema_version": 1, "bridges": {}}, "applied": False}]
    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "homekit_manager/history"})
    response = await client.receive_json()
    assert response["success"] is True
    assert response["result"]["count"] == 1
    await client.send_json_auto_id({"type": "homekit_manager/history_restore", "index": 0})
    response = await client.receive_json()
    assert response["success"] is True
    assert response["result"]["restored"] is True
    assert response["result"]["applied"] is False


async def test_homekit_manager_unknown_bridge_selection_is_blocked(
    hass, enable_custom_integrations, hass_ws_client
):
    """A draft context cannot be switched to an arbitrary bridge ID."""
    result = await hass.config_entries.flow.async_init(
        "homekit_manager", context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "homekit_manager/select_bridge", "entry_id": "not-a-live-bridge"})
    response = await client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "unknown_bridge"


async def test_homekit_manager_performance_summary_is_bounded(
    hass, enable_custom_integrations, hass_ws_client
):
    """Performance information is a bounded read-only summary."""
    result = await hass.config_entries.flow.async_init(
        "homekit_manager", context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "homekit_manager/performance"})
    response = await client.receive_json()
    assert response["success"] is True
    assert "recommended_page_size" in response["result"]
