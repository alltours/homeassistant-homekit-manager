# HomeKit Manager 0.10.32-rc.1

This release candidate contains the native Write/Apply reliability hardening
for isolated acceptance testing. It is not an official stable release.

## Scope

- dependency-injected fault-injection points for isolated Apply and rollback
  crash testing;
- explicit versioning as `0.10.32-rc.1`;
- unchanged Write-Grant, Apply, native-filter, pairing, and HAP-persistence
  security boundaries;
- reproducible release-build metadata.

The fault-injection hooks are test-only injection points. The production
coordinator does not provide a fault injector.

## Verification boundary

The real isolated Core/HAP Apply acceptance covers paired multi-bridge
operation and controller reconnect. The complete SIGKILL crash matrices for
native Apply and rollback remain separate release gates and must be reported
explicitly; this document does not claim those gates are passed.

The experimental UI↔YAML Core migration patch remains isolated from the
HomeKit Manager release package and does not enable production migration.

No production Home Assistant instance, Config Entry, native filter, pairing,
HAP persistence, or `.storage` file is modified by this release candidate.
