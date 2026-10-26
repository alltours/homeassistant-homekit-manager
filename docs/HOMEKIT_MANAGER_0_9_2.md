# HomeKit Manager 0.9.2

## Version strategy

Starting with this release, the project uses the `0.9.x` series. Existing `1.0.x`
tags and releases remain historical and are not rewritten or re-labelled.

## Delivered changes

- Four-panel navigation: Übersicht, Entitäten, Konfiguration, Änderungen.
- Overview cards for bridge, entity, compatibility, availability, drafts, and sync state.
- Responsive entity management with search, filters, sorting, pagination, details, and bulk actions.
- Central per-bridge management-mode state for YAML, HomeKit Bridge, and HomeKit Manager.
- A six-direction migration matrix. Cross-mode activation remains blocked because
  Home Assistant does not provide a supported guarantee that bridge identity,
  pairings, accessory IDs, and instance IDs survive an automatic migration.
- Draft validation, optimistic concurrency, deterministic YAML export, and read-only
  HomeKit protection remain active.
- Ordinary `hass.states` setter updates no longer trigger a full inventory refresh.

## Security boundary

`apply_enabled = False` remains mandatory. The writer never updates an existing
HomeKit config entry, reloads HomeKit, changes pairings, edits `.storage`, or creates
a second bridge. Mode selection records a desired mode only; it does not activate a
risky migration.

## YAML limitation

Home Assistant supports YAML HomeKit configuration, but UI-created HomeKit entries
must be managed through the UI. The manager therefore does not automatically inject
an include into `configuration.yaml` or replace an existing bridge. A future migration
requires an explicit, separately verified workflow.

## Verification

The release is validated with Python compilation, JSON validation, JavaScript syntax
checking, frontend behavior tests, Home Assistant integration tests, and secret scans.
