# HomeKit Manager 0.10.5 development checkpoint

## Starting point

- Base: released v0.10.4, commit `94d8e30` on `origin/main`.
- Branch: `feature/homekit-manager-0.10.5-production`.
- Productive Home Assistant, HomeKit configuration and pairing state were not modified.

## Completed, 2026-10-29

- Device and area bulk actions now omit hidden, disabled, diagnostic,
  configuration, unsupported and unknown-compatibility entities by default.
  The confirmation shows separate exclusion reasons. The two actions are
  labelled “Alle einschließen” and “Alle ausschließen”. A group whose members
  all have unknown filter status no longer claims to have no entities.
- Browser tests for these cases pass in Chromium and WebKit. The complete
  current browser suite passes: 76 tests.

## Open release gates

- Default production Apply is still gated by the older local-grant/test-mode
  authority. The new operation-bound authorization and negative tests remain.
- A positive-list migration and invariant are not implemented. An empty Core
  filter means *include all*, so an empty include list is never a safe deny-all
  migration. Broad current rules cannot be converted without a proven export
  set and explicit migration confirmation.
- Final backend, integration, HAP, performance, security and CI checks, version
  bump, documentation, PR and release are outstanding. Do not publish 0.10.5
  until these gates are actually satisfied.

## Next concrete step

Implement an operation-bound production authority for supported existing
Bridge entries, checked again at the native/YAML mutation boundary. Preserve
the admin, exact-operation confirmation, full revision, backup, verification
and no-retry guards. Add focused negative tests before changing UI status.
