# HomeKit Manager 0.10.8

## Scope

0.10.8 is a diagnostics and migration-preparation release. It does not
install itself on Home Assistant, change a native HomeKit filter, reload a
bridge, change pairings, or write `.storage/homekit.*`.

## Inventory export

The read-only `homekit_manager/inventory_export` administrator WebSocket
command exports the coordinator's last atomic snapshot as `json` or `csv`.
Rows are sorted by Entity-ID and include registry, device, area, integration,
availability, compatibility, native-filter, Manager-decision and runtime
publication evidence. The JSON envelope includes the timestamp, revision,
fingerprint and completeness checks. State attributes and current state values
are deliberately excluded.

`complete` is true only when the registry/state union is represented exactly,
without missing or duplicate entity IDs. A false value must be treated as an
incomplete diagnostic result, not as evidence that entities do not exist.

## Runtime diagnosis

When the selected HomeKit Config Entry exposes the running
`runtime_data.homekit.bridge.accessories` collection, the adapter reads the
already-created accessory objects without invoking lifecycle methods. It
records redacted accessory fingerprints, entity IDs, service types and
characteristic types/counts. Accessory IDs are hashed; pairing IDs, private
keys, HAP persistence and state values are never returned.

The adapter reports `published_verified` only for an unambiguous mapped
accessory. It reports `not_published_verified` only if the complete relevant
collection was readable and no ambiguity remained. Otherwise the result is
`unknown` or `mapping_ambiguous`. A partial result may show confirmed rows but
must not be interpreted as a complete negative publication list.

## Positive-list workflow

Use the Devices view to inspect areas, devices and entity IDs. Bulk actions
remain draft-only and show the server-calculated concrete entity set before
confirmation. The diagnostics view exposes the three independent observations:

1. Native filter: what Home Assistant's stored filter selects.
2. Manager decision: what was explicitly stored as include or exclude.
3. Runtime publication: what the current HAP object graph proves.

Do not treat recommendations, legacy domain matches or currently visible Apple
Home accessories as consent. A positive-list migration requires an explicit
user-confirmed set. New devices and entities remain outside that set.

## Verification boundary

The runtime adapter is deliberately read-only and version-tolerant. If a Core
version does not expose the expected objects, the UI shows `unknown` and the
export retains the reason. This is safer than attempting to reconstruct HAP
state from persistence files or triggering a reload. Physical Apple Home
visibility and Siri latency are not claimed by this release.

## Safe installation later

Install only after reviewing the release artifact and checksum, taking a
Home-Assistant backup, and confirming that the production Config Entry,
pairings, bridge identity and native filter are unchanged. After installation,
perform a read-only inventory and runtime diagnosis first. Any later native
filter Apply remains a separate, explicitly authorized operation subject to
the existing revision, positive-list, empty-list, source and rollback gates.
