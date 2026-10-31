# ADR-014: Core-owned HomeKit source migration proof of concept

Status: experimental, not enabled for production

## Decision

The HomeKit Manager remains fail-closed on Home Assistant versions without a
Core-owned migration boundary. The isolated 0.10.14 prototype places the
critical boundary in `homeassistant.components.homekit.async_setup`, after
Config Entries have been loaded but before the native YAML reconciliation is
started. Core owns the persisted request, source mutation, YAML filtering and
post-HAP verification. The Manager only submits a strictly shaped request in
the isolated test harness and reports capability status.

The Core boundary must:

- validate entry ID, source, target, name, port, MAC and allowlist;
- persist target data/options before the source mutation;
- force-persist the Config Entry set at the source-switch boundary;
- filter only an unambiguous matching YAML bridge;
- fail closed on missing/corrupt/ambiguous state or stale YAML;
- finalize only after the bridge has started and its MAC matches.

## Deliberate limitations

This is not an upstream-ready API. The prototype uses Core internals for the
experimental storage transaction and does not claim filesystem-level atomicity
across Config Entry storage, YAML files and HAP persistence. A process crash
before the durable source switch is blocked for manual recovery; it is never
replayed optimistically. The production Manager UI and WebSocket start action
remain disabled.

The tested migration writes/removes the isolated YAML source as part of the
test setup. A real product implementation would need a Core-owned, provenance-
aware YAML edit contract before it could safely remove or replace user files.

## Evidence

The full-Core worker uses a real Home Assistant process, a loopback HAP bridge,
an aiohomekit pairing and a SIGKILL between the durable source switch and
restart. Both UI→YAML and YAML→UI were exercised on Core 2026.10.4; the beta
checkout received the same patch and passed syntax/import validation, while a
full beta bootstrap remains separately environment-dependent.
