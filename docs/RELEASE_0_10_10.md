# HomeKit Manager 0.10.10

## Scope

0.10.10 makes the difference between Manager decisions, native filter
selection and runtime evidence explicit. Each reconciliation deviation has a
stable identifier, classification, source, cause and severity and is listed in
the Changes view.

The release also supports a deliberate exact Entity-ID selection for enabled,
HomeKit-compatible hidden entities. Hidden entities remain excluded from area
and device bulk actions. They are visibly marked and require an explicit
individual selection. Disabled, technical, unsupported and unknown entities
remain blocked.

## Legacy 60/54 state

For an explicit-overrides document with 54 current Manager exclusions and six
native `explicit_include` entities without a Manager decision, the UI reports
60 concrete rows:

- 54 `manager_exclude_native` rows.
- 6 `native_explicit_unmanaged` rows.

The total is derived from the listed deviation rows. Stale or invalid Manager
decisions receive their own classifications and are never silently deleted.

## Hidden entities

Home Assistant Core accepts an exact `include_entities` override for a hidden
registry entry. HomeKit Manager permits that exception only when the entity is
enabled, has a current state, has a registry entry, is HomeKit-compatible and
has no technical entity category. Hidden entries are not automatically added by
migration or bulk actions.

## Safety boundary

This release does not perform a productive Apply during development or tests.
Native filter writing remains protected by the existing revision, fingerprint,
confirmation, source, runtime and rollback gates. Pairing data, bridge
identity, AID/IID persistence and Home Assistant registries are not modified by
diagnosis or draft operations.
