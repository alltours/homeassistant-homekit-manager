# HomeKit Manager 0.10.3

## Scope

The Devices tab now presents areas, devices and entities as one expandable
hierarchy. Each entity appears once. Devices use their Home Assistant device
area; a different entity-specific area remains visible in the entity row.
Entities without a device are represented as individual entries under their
entity area, and devices without an area appear under “Ohne Bereich”.

Area and device rows show the current and planned aggregate filter states.
An unknown-only group has no evaluable status. Explicit “Alles einschließen”
and “Alles ausschließen” actions show a confirmation with the full device and
entity scope, new changes, already matching entries and blocked entries.
Search, filters and pagination affect display only; the action always targets
the full chosen area or device. Confirmation only updates the Manager draft.
The existing server-side preview, revision checks and separately confirmed
Apply remain mandatory. A filter match is not proof of HAP publication or
Apple Home visibility.

The operation plan now counts effective entity changes rather than unchanged
overrides already present in a saved draft and blocks drafts with no effective
change. Expanded technical details survive
passive inventory refreshes. When no Apply operation exists, the Changes tab
shows “Keine Anwendung protokolliert” instead of an unknown outcome.

## Compatibility and safety

Native `SOURCE_USER` Bridge filter writing remains restricted to isolated-tested
Core 2026.10.4 and 2026.11.0b0. Supported YAML writing remains restricted to
2026.10.4. This release does not add another write path, change Pairing storage,
authorize an existing production Bridge or install itself. The optional native
test mode still requires an administrator, an exact Bridge, a current operation
plan and separate confirmation; it expires after one hour. Physical Apple Home
pairing preservation is untested.

## Upgrade and rollback

Before installation, verify a restorable Home Assistant backup and retain the
current Bridge filter for a targeted reversal. Replace only the integration
files with the verified 0.10.3 ZIP and restart Core only with separate approval.
Check the version, area placement, counts and saved drafts read-only before
enabling any writing. Rolling back the integration files to 0.10.2 and
restarting Core requires separate approval. A code rollback does not reverse a
HomeKit filter change; reconcile any operation and seek explicit approval for
a new inverse filter plan. Never edit `.storage/homekit.*` for this purpose.
