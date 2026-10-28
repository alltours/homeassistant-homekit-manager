"""Measure Core inventory refresh and authenticated WebSocket transport separately."""
from __future__ import annotations

import json
import logging
from statistics import median
from time import perf_counter

from homeassistant import loader
from homeassistant.helpers import area_registry, device_registry, entity_registry
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homekit_manager.coordinator import HomeKitManagerCoordinator


@pytest.mark.parametrize("count", [100, 500, 1216, 5000])
async def test_inventory_refresh_and_websocket_scale(hass, enable_custom_integrations, hass_ws_client, caplog, count):
    caplog.set_level(logging.WARNING, logger="homeassistant.helpers.entity_registry")
    # Core's debug WebSocket logger includes the ephemeral auth token and the
    # complete inventory payload. Keep both out of benchmark logs.
    caplog.set_level(logging.WARNING, logger="homeassistant.components.websocket_api.http.connection")
    domains = ("light", "sensor", "switch", "binary_sensor")
    assert "homekit_manager" in await loader.async_get_custom_components(hass)
    MockConfigEntry(
        domain="homekit", entry_id="isolated-performance-bridge", source="user",
        data={"name": "Performance Fixture", "port": 21095},
        options={"mode": "bridge", "filter": {"include_domains": list(domains)}},
    ).add_to_hass(hass)
    flow = await hass.config_entries.flow.async_init("homekit_manager", context={"source": "user"})
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    manager: HomeKitManagerCoordinator = hass.data["homekit_manager"]["coordinator"]
    # Measure manual refresh without a second background refresh from the
    # synthetic registry-creation burst; event coalescing has separate tests.
    for unsubscribe in manager._unsubscribers:
        unsubscribe()
    manager._unsubscribers.clear()
    registry = entity_registry.async_get(hass)
    manager_entry = hass.config_entries.async_entries("homekit_manager")[0]
    devices = device_registry.async_get(hass)
    areas = area_registry.async_get(hass)
    area_ids = [areas.async_get_or_create(f"Performance Area {index:03d}").id for index in range(100)] if count == 5000 else []
    for index in range(count):
        domain = domains[index % len(domains)]
        device_id = None
        if count == 5000:
            device = devices.async_get_or_create(
                config_entry_id=manager_entry.entry_id,
                identifiers={("hkm_perf_fixture", f"device-{index}")},
                name=f"Performance Device {index:04d}",
            )
            devices.async_update_device(device.id, area_id=area_ids[index % len(area_ids)])
            device_id = device.id
        item = registry.async_get_or_create(
            domain, "hkm_perf_fixture", f"perf-{index}", suggested_object_id=f"perf_{index}",
            device_id=device_id,
        )
        hass.states.async_set(item.entity_id, "unavailable" if index % 20 == 0 else "on",
                              {"hidden_backend_attribute": "not sent in inventory pages"})
    await hass.async_block_till_done()
    client = await hass_ws_client()
    refresh_ms, websocket_ms, payload_bytes = [], [], []
    for _ in range(3):
        await manager.async_refresh()
        refresh_ms.append(manager.refresh_duration_ms)
        started = perf_counter()
        await client.send_json_auto_id({"type": "homekit_manager/inventory", "offset": 0, "limit": 500,
                                        "include_context": True})
        response = await client.receive_json()
        assert response["success"] is True
        result = response["result"]
        assert all("attributes" not in item for item in result["entities"])
        revision, fingerprint, total = result["snapshot_revision"], result["fingerprint"], result["total"]
        ids = [item["entity_id"] for item in result["entities"]]
        received = len(result["entities"])
        encoded_size = len(json.dumps(response).encode())
        context_page_bytes = encoded_size
        largest_page = encoded_size
        pages = 1
        while received < total:
            await client.send_json_auto_id({"type": "homekit_manager/inventory", "offset": received, "limit": 500})
            page = await client.receive_json()
            assert page["success"] is True
            payload = page["result"]
            assert payload["snapshot_revision"] == revision and payload["fingerprint"] == fingerprint
            assert payload["offset"] == received and payload["total"] == total and payload["entities"]
            received += len(payload["entities"])
            ids.extend(item["entity_id"] for item in payload["entities"])
            page_bytes = len(json.dumps(page).encode())
            encoded_size += page_bytes
            largest_page = max(largest_page, page_bytes)
            pages += 1
        websocket_ms.append((perf_counter() - started) * 1000)
        assert received >= count
        assert len(ids) == len(set(ids)) == total and ids == sorted(ids)
        payload_bytes.append(encoded_size)
    if count == 5000:
        assert len(manager.devices) == 5000 and len(manager.areas) == 100
        group_max_page_bytes = 0
        for route, key, expected in (("homekit_manager/devices", "devices", 5000),
                                     ("homekit_manager/areas", "areas", 100)):
            received = 0
            while received < expected:
                await client.send_json_auto_id({"type": route, "offset": received, "limit": 500})
                grouped_response = await client.receive_json()
                assert grouped_response["success"] is True
                grouped_page = grouped_response["result"]
                assert grouped_page["total"] == expected and grouped_page["offset"] == received
                assert grouped_page["snapshot_revision"] == manager.refresh_count
                assert len(grouped_page[key]) <= 500
                grouped_page_bytes = len(json.dumps(grouped_response).encode())
                group_max_page_bytes = max(group_max_page_bytes, grouped_page_bytes)
                assert grouped_page_bytes < 4 * 1024 * 1024
                received += len(grouped_page[key])
            assert received == expected
        await client.send_json_auto_id({"type": "homekit_manager/inventory", "query": "perf_4999",
                                        "offset": 0, "limit": 500})
        search = await client.receive_json()
        assert search["success"] is True
        assert search["result"]["total"] == 1
        assert search["result"]["entities"][0]["entity_id"].endswith("perf_4999")
    metrics = {"entities": count, "rounds": 3, "pages": pages,
               "max_page_bytes": largest_page, "refresh_median_ms": round(median(refresh_ms), 2),
               "websocket_median_ms": round(median(websocket_ms), 2),
               "payload_bytes": round(median(payload_bytes))}
    if count == 5000:
        metrics.update({"context_page_bytes": context_page_bytes,
                        "group_max_page_bytes": group_max_page_bytes,
                        "registry_devices": len(manager.devices), "registry_areas": len(manager.areas)})
    print("HKM_PERFORMANCE", json.dumps(metrics, sort_keys=True))
    assert largest_page < 4 * 1024 * 1024
    assert max(refresh_ms) < 15000 and max(websocket_ms) < 15000


@pytest.mark.parametrize("page", [{"offset": -1}, {"limit": 501}])
@pytest.mark.parametrize("route", ["homekit_manager/inventory", "homekit_manager/devices", "homekit_manager/areas"])
async def test_inventory_rejects_unbounded_or_negative_page(hass, enable_custom_integrations, hass_ws_client, page, route):
    assert "homekit_manager" in await loader.async_get_custom_components(hass)
    flow = await hass.config_entries.flow.async_init("homekit_manager", context={"source": "user"})
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    client = await hass_ws_client()
    await client.send_json_auto_id({"type": route} | page)
    response = await client.receive_json()
    assert response["success"] is False and response["error"]["code"] == "invalid_pagination"
