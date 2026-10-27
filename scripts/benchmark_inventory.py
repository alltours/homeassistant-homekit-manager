#!/usr/bin/env python3
"""Reproducible isolated inventory computation benchmark.

This measures the common pure computation path, not a live HA coordinator or
network/browser latency. Use --source-root to compare two checked-out commits.
"""
from __future__ import annotations

import argparse
import gc
import json
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from types import SimpleNamespace as NS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--rounds", type=int, default=30)
    parser.add_argument("--entities", type=int, default=1172)
    parser.add_argument("--devices", type=int, default=129)
    args = parser.parse_args()
    if args.entities < 1 or args.devices < 1 or args.rounds < 2:
        parser.error("entities and devices must be positive; rounds must be at least two")
    sys.path.insert(0, str(args.source_root.resolve()))
    from custom_components.homekit_manager.inventory import build_inventory
    from custom_components.homekit_manager.grouping import build_area_views, build_device_views
    from custom_components.homekit_manager.diagnostics import build_diagnostics
    from custom_components.homekit_manager.compatibility import classify_entity
    from custom_components.homekit_manager.filtering import build_core_filter, evaluate_filter

    devices = {f"device-{i}": NS(name=f"Device {i}", area_id=f"area-{i % 18}") for i in range(args.devices)}
    areas = {f"area-{i}": NS(name=f"Area {i}") for i in range(18)}
    entities = {}
    states = {}
    for i in range(args.entities):
        domain = ("light", "sensor", "switch", "binary_sensor")[i % 4]
        entity_id = f"{domain}.benchmark_{i:04d}"
        entities[entity_id] = NS(entity_id=entity_id, name=None, original_name=None,
                                 device_id=f"device-{i % args.devices}", area_id=None, platform="benchmark",
                                 device_class="temperature" if domain == "sensor" else None,
                                 original_device_class=None, entity_category=None,
                                 disabled_by=None, hidden_by=None, config_entry_id="isolated")
        states[entity_id] = NS(state="unavailable" if i % 20 == 0 else "on",
                               attributes={"friendly_name": f"Benchmark {i}"})
    registry = {"entities": entities}
    device_registry = {"devices": devices}
    area_registry = {"areas": areas}
    config_filter = {"include_domains": ["light", "sensor", "switch", "binary_sensor"]}
    core_filter = build_core_filter(config_filter)

    def run() -> tuple[int, int]:
        records = build_inventory(registry, device_registry, area_registry, states)
        inventory = []
        for record in records:
            item = record.as_dict()
            item["compatibility"] = classify_entity(record).as_dict()
            item["homekit"] = evaluate_filter(record.entity_id, record.entity_category,
                                               record.hidden_by, config_filter, core_filter).as_dict()
            inventory.append(item)
        devices_view = build_device_views(inventory)
        build_area_views(inventory)
        build_diagnostics(inventory, [{"entry_id": "isolated", "filter": config_filter}], {"valid": True})
        return len(inventory), len(devices_view)

    run()  # Warm imports and caches.
    gc.collect()
    wall, cpu = [], []
    tracemalloc.start()
    for _ in range(args.rounds):
        start_wall, start_cpu = time.perf_counter(), time.process_time()
        counts = run()
        wall.append((time.perf_counter() - start_wall) * 1000)
        cpu.append((time.process_time() - start_cpu) * 1000)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(json.dumps({"source_root": str(args.source_root.resolve()), "rounds": args.rounds,
                      "entity_count": counts[0], "device_reference_count": counts[1],
                      "wall_median_ms": round(statistics.median(wall), 3),
                      "wall_p95_ms": round(sorted(wall)[int((len(wall)-1)*.95)], 3),
                      "cpu_median_ms": round(statistics.median(cpu), 3),
                      "tracemalloc_peak_bytes": peak}, sort_keys=True))


if __name__ == "__main__":
    main()
