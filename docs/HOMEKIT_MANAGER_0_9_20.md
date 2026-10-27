# HomeKit Manager 0.9.20: architecture and release notes

Status: local release candidate, 27 October 2026. No production HomeKit write, reload, migration, installation, tag or publication is part of this version. The reference is Core 2026.10.4 and Manager commit `4a4e73434e57ce3c1e66ae7f700c3d05328b7e97` (0.9.19).

## Inventory semantics

The Manager inventory is the union of Entity Registry entries and state-only entities. Its `device_count` counts distinct `device_id` references on those entities. The native device-list WebSocket enumerates `registry.devices` and `registry.child_devices`. Since Core 2026.8, `DeviceRegistry.async_get(id)` may synthesize a former composite device while that ID is absent from both enumerable collections. This is an evidenced mechanism for a Manager count exceeding the native list count; it is **not evidence that the eight production IDs are composites**. Version 0.9.20 exposes all denominators and the composite/missing reference ID lists to admins. A visible device with no inventory entity causes the reverse difference. The native UI can further filter by area, integration, search, and visibility. Never repair a count merely by forcing it to 121.

`availability_status` is exclusive, in this precedence: `disabled` (entity or device registry disabled), `orphaned` (referenced device ID definitively absent from an available Device Registry), `no_state` (registry entity has no current State), `unavailable` (literal HA state), `unknown` (literal HA state), `available` (any other current state). A state-only entity with no device ID is not orphaned. If the registry is inaccessible, device integrity is `unknown` and an active state is still classified `available`. The separate raw `state` and `device_registry_status` fields retain the underlying evidence.

Compatibility is a Core 2026.10.4 projection, never a publication proof. The five evidence levels are: inventory present; selected bridge filter inclusion `true/false/unknown`; technical support `supported/conditional/unsupported/unknown`; actual HAP publication `unknown` unless a separate reliable runtime probe exists; Apple Home visibility `unknown` unless directly tested. Unsupported entities are critical only when the selected bridge filter definitely includes them, and the finding still does not claim publication. Excluded/undetermined unsupported entities are informational. Uncertain compatibility and availability findings are actionable only when definitely included. Explicit assignment in two bridge filters is a warning because multiple bridges can intentionally expose an entity.

## Refresh and performance

The Coordinator listens to state, entity, device, and area registry changes. `homekit_state_change` is an action event; actual state changes already emit `state_changed`, so it no longer triggers a redundant inventory refresh. State events with equal old/new state and attributes are counted and ignored. Other events are coalesced with the existing one-second interval; a pending event during I/O causes another complete pass. Snapshot publication remains atomic. The frontend renders once for an automatic refresh and tracks revisions so that an event arriving while a WebSocket read is in flight causes a follow-up read if needed. Failed reads do not retry in a busy loop.

The admin performance endpoint now reports events by source, ignored events, refresh requests, completed recomputations, elapsed and process CPU time, and elapsed time for registry/inventory, filter/compatibility, grouping, source I/O, and diagnostics/fingerprint phases. CPU time is process-wide and may include concurrent tasks. Isolated `scripts/benchmark_inventory.py` measures 1,172 records, 129 device references, median/p95 wall and CPU time and Python allocation peak. It excludes HA executor wait, WebSocket serialization/network, the browser, and production workloads. A 320 ms production refresh is therefore not directly comparable to this pure computation benchmark. The 368/10-minute production refresh count cannot be reproduced or attributed without authenticated event traces.

| Isolated common pipeline, 100 rounds, Core 2026.10.4 | 0.9.19 `4a4e734` | 0.9.20 candidate |
|---|---:|---:|
| Wall median | 52.230 ms | 48.561 ms |
| Wall p95 | 53.219 ms | 49.635 ms |
| CPU median | 52.232 ms | 48.563 ms |
| Python allocation peak (`tracemalloc`) | 2,202,914 bytes | 2,300,761 bytes |

The median computation time fell 7.0%; the allocation peak rose 4.4% because the snapshot carries two new classification fields. Neither result measures resident process memory. A synthetic burst of 100 identical state events plus 25 changed events produced one full recomputation after coalescing; this establishes only the tested event sequence, not a production frequency reduction.

## Long-term configuration contract

Exactly one authoritative source per bridge: `source=user` native Config Entry or `source=import` YAML-backed Config Entry. The Manager draft/history remains a temporary workspace and never becomes a third active source. A future common, immutable `HomeKitConfiguration` should include source kind, Core version, bridge entry ID, raw `data`, raw `options`, normalized effective values, filter, entity config, mode, name, port, opaque unrecognized fields, provenance (file/include chain or entry), hashes/revisions, and evidence levels. Unknown fields are retained and make conversion ineligible until reviewed. Secret values must be redacted in UI and audit logs, without dropping them from a proposed conversion silently.

Proposed read/plan interface for both `NativeHomeKitAdapter` and `YamlHomeKitAdapter`: `discover()`, `read_snapshot(target)`, `capabilities(snapshot)`, `validate(candidate)`, `compare(before, candidate)`, `plan(candidate, expected_revision)`, `verify(observation)`. Future write operations are **not implemented** in 0.9.20. A plan names the one target, exact field-level diff, external side effects, unsupported fields, expected revision, validation result, reload requirement, identity risk, rollback artifact, and verification probes. A conflict is a changed Config Entry revision, changed file bytes/include graph, changed source, ambiguous bridge mapping, version drift, conflicting port/name, unknown option or access failure. On any conflict, fail closed and re-read.

### Native adapter

Read `config_entries.async_entries("homekit")`, distinguish `SOURCE_USER` from `SOURCE_IMPORT`, and read `data` and `options` separately. For user entries, the native Options Flow is the integration-owned editing path. `hass.config_entries.async_update_entry(entry, options=...)` is a documented API for changing entry options, but calling it from a different integration bypasses the HomeKit Options Flow's user-facing validation and scope. In Core 2026.10.4, the HomeKit options update listener reloads user entries; imported entries instead return without reload. A future native writer would need an integration-version-specific validator, a complete before/after comparison, one-entry scope, a confirmed maintenance window, rollback evidence, and a post-reload check. None is enabled now.

### YAML adapter

Read the actual `configuration.yaml` graph with Home Assistant's include semantics, including `!include`, four `!include_dir_*` variants, nested includes and packages. HomeKit can be one mapping or a list of bridges. A future adapter must prove the exact file and node that supplies each bridge, using the full include path, unique name and port, and parsed Core configuration. A textual match or an existing `homekit_manager.yaml` is insufficient. Multiple candidate files, merge operations, aliases, duplicate names/ports, external symlinks, `!secret`, unknown tags, or unreadable files block automatic editing. The current `config_source.py` is only a read-only hint and must not be promoted to an edit target.

For an unambiguous explicitly selected file, a future writer would need a byte hash and inode/mtime precondition for every graph node, permission check, same-directory temporary file, fsync, atomic replace, verifiable backup, and lock. Comments, order and formatting require a round-trip YAML editor or exact text edit with a proof of unchanged surrounding content; generic PyYAML reserialization is insufficient. Validate an isolated copy with Core 2026.10.4 schema and `hass --script check_config`; then recheck hash immediately before replacement. `homekit.reload` reloads YAML-defined instances only; it is never called in 0.9.20. After a future reload, compare the imported Config Entry `data/options` and effective filter to the plan. A failed check or unknown outcome blocks automatic retry; rollback of bytes alone does not prove HAP identity or Apple Home recovery.

## Bidirectional conversion matrix (Core 2026.10.4)

“Lossless” means preserving the configuration value in a representation accepted by the target syntax. It does **not** mean preserving Bridge identity, pairing, active publication or Apple Home state. The UI target means the supported native HomeKit Options Flow, not arbitrary internal option injection.

| Setting | Native → YAML | YAML → native UI | Constraint / evidence |
|---|---|---|---|
| `include_domains`, `exclude_domains` | Lossless | Limited | Options Flow presents domain and include/exclude choices; mixed filter rules may not round-trip. |
| `include_entities`, `exclude_entities` | Lossless | Limited | Native flow may recalculate the filter; exact effective set must be compared. |
| `include_entity_globs`, `exclude_entity_globs` | Lossless | Limited | YAML schema supports globs; native flow does not expose every combination. |
| `entity_config` names | Lossless as YAML | Not transferable in general | YAML exposes per-entity names; Apple Home may cache the first name. |
| `entity_config` linked sensors, thresholds, codes, media/camera options | Lossless if schema-valid and secret handling is proven | Not transferable in general | Native Options Flow supports only a subset. Unknown nested keys block. |
| Climate `entity_config.type` | Lossless | Limited | Current native flow can choose Thermostat/HeaterCooler; other entity config keys do not follow automatically. |
| Mode `bridge` | Lossless as value | Limited | New entry creation and identity are separate concerns. |
| Mode `accessory` plus one entity | Limited | Limited | One accessory per entry, mode-specific setup and pairing. Multiple entities block. |
| Name and port | Lossless as values | Limited | Uniqueness and port availability must be checked; changing a port may affect discovery. |
| `ip_address`, `advertise_ip` | Lossless if present | Not transferable via UI | Documented YAML settings; not general UI flow fields. |
| `devices` trigger list | Lossless if accepted by schema | Limited | Flow may derive or overwrite values. |
| YAML `!include`, comments, anchors, `!secret`, formatting | Not applicable | Not transferable | They are file/source structure, not Config Entry options. Preserve on YAML edits. |
| `SOURCE_USER` / `SOURCE_IMPORT`, entry ID | Not transferable | Not transferable | Source and identity are entry metadata, not HomeKit settings. |
| HAP pairing state, bridge MAC, AID/IID stores | Not transferable | Not transferable | Separate persistence tied to entry ID; must never be inferred from conversion. |
| Unknown/current or future keys | Unknown — block | Unknown — block | Explicit review and Core version check required. |

No conversion silently removes a key. Every omission, transformation and uncertainty must be listed in a machine-readable diff and accepted separately in a future release. The 0.9.20 UI does not offer conversion.

The Core 2026.10.4 `entity_config` validator was checked key by key. The table's “entity_config linked sensors, thresholds, codes, media/camera options” row covers: `linked_battery_sensor`, `linked_battery_charging_sensor`, `low_battery_threshold`, `linked_doorbell_sensor`, `linked_humidity_sensor`, `linked_pm25_sensor`, `linked_temperature_sensor`, `linked_filter_change_indication_binary_sensor`, `linked_filter_life_level_sensor`, `linked_obstruction_sensor`, `linked_motion_sensor`, `linked_valve_duration`, `linked_valve_end_time`, `co_threshold`, `co2_threshold`, `code`, `feature_list` with `feature`, `stream_address`, `stream_source`, `audio_codec`, `support_audio`, `max_width`, `max_height`, `max_fps`, `audio_map`, `video_map`, `stream_count`, `video_codec`, `video_profile_names`, `audio_packet_size`, and `video_packet_size`. `type` is domain-specific for climate, fan, switch and valve. For each of these, native → YAML is value-preserving only if that domain's YAML schema accepts it; YAML → native UI is **not generally transferable** unless the current Options Flow exposes the exact field. All domain/key combinations must be schema-tested. Core's top-level `BRIDGE_SCHEMA` also allows extra keys, but extra-key acceptance is not evidence that HomeKit will use them; such keys are **unknown** and block conversion.

## Identity and repeated migration

Core 2026.10.4 names the HomeKit `.storage` state, AID and IID files with `entry_id`; the driver loads its persisted MAC and HAP state from the entry-specific file. Removing a HomeKit entry calls `remove_state_files_for_entry_id`, which deletes all three files. Existing AID allocations are keyed by entity/device identity, and changes to entity IDs or device grouping can alter Home app identity even if entry ID stays constant. An unchanged entry ID is **necessary-looking but not sufficient proof** for pairing preservation; the actual HAP state, MAC, port, advertisements, accessories and Apple Home behavior must be checked in an isolated paired test.

`async_update_entry` has no `source` parameter. Changing `SOURCE_USER` to `SOURCE_IMPORT` on an existing entry would require a private attribute/storage manipulation or Core change; HomeKit's import reconciliation only indexes already-imported entries by name/port. After restart or `homekit.reload`, a new YAML import could therefore create another entry instead of adopting the user entry. The reverse direction also lacks a supported source mutation. Repeating UI → YAML → UI → YAML → UI multiplies duplicate-entry, state-file deletion, port conflict, pairing and AID/IID risks. No paired Apple Home test environment was available for 0.9.20, so pairing preservation and repeated migration are **NOT TESTED**.

## Decision record

Scales: high/medium/low favorability; “unknown” means no evidence. Pairing is not claimed preserved.

| Approach | Safety | Maintenance/HA compatibility | Pairing | Migration | Recovery/UX | Cost/update risk |
|---|---|---|---|---|---|---|
| A. Manage each existing source directly | High with strict adapter gates | Medium/high | No source change needed | None | Source-specific rollback; clear UX | Medium/medium |
| B. Keep entry, switch source | Low | Low: no public source setter | Unknown | High in theory | Hard to recover after import/restart | High/high |
| C. Export to new bridge | Medium if explicit | High supported creation paths | New pairing expected | One-way possible | Clear rollback by retaining old bridge, but duplicate-port risk | Medium/medium |
| D. Keep YAML authoritative, manage through Manager | Medium when exact file proven | Medium | No source change needed | None | Comments/includes and file conflict complexity | High/medium |

**Decision for 0.9.20:** A as the long-term foundation, using D as its YAML implementation. Keep B as research only; do not ship source mutation. C may later be an explicit new-identity export workflow after isolation and user acceptance, never an identity-preserving migration claim. Every adapter will read from the actual authoritative source. The draft is only a temporary plan. No productive writer is enabled.

## Evidence sources

- [HomeKit Bridge documentation](https://www.home-assistant.io/integrations/homekit/) documents YAML schema, UI/YAML separation, pairing files, AID limits, accessory mode and reload.
- [HomeKit reload action](https://www.home-assistant.io/actions/homekit.reload/) applies only to YAML instances.
- [Configuration splitting](https://www.home-assistant.io/docs/configuration/splitting_configuration) documents all include variants.
- [Configuration check](https://www.home-assistant.io/docs/tools/check_config/) documents isolated validation.
- [Altering Config Entries](https://developers.home-assistant.io/blog/2024/02/12/async_update_entry/) documents the supported update method and its fields.
- Exact installed Core 2026.10.4 source inspected locally: `homeassistant/components/homekit/__init__.py`, `config_flow.py`, `util.py`; `homeassistant/config_entries.py`; `homeassistant/helpers/device_registry.py`; `homeassistant/components/config/device_registry.py`. Claims about source mutation, import reconciliation and synthetic composites are tied to this version, not a future compatibility promise.
