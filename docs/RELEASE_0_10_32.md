# HomeKit Manager 0.10.32

HomeKit Manager 0.10.32 is the stable release of the native write/apply and
rollback workflow.

## Included

- Native HomeKit filter preview and explicitly authorized Apply.
- Explicit Native Rollback, including recovery after a Home Assistant restart.
- Persistent operation journal with versioning, integrity and consistency
  checks, and fail-closed recovery.
- Independent administrator, confirmation, revision, fingerprint, lock and
  Write-Grant checks before native mutation.
- Two-bridge and isolated HAP-controller acceptance coverage.

## Security semantics

The operations journal uses an unkeyed SHA-256 digest for corruption and
consistency detection. It is not a cryptographic authenticity mechanism
against an attacker who can modify the journal and recompute the digest.
Native writes remain independently authorized and verified. Unknown or
contradictory states never trigger an automatic retry or rollback.

## Compatibility

The release was tested with Home Assistant Core 2026.10.4 and 2026.11.0b0
using isolated Core processes and HAP test controllers. HAP-controller
reconnect and multi-bridge isolation were verified; this is not a physical
Apple Home reconnect test.

## Limitations

- UI↔YAML migration remains disabled.
- No automatic filter migration is performed.
- Legacy in-flight operation journals may require manual read-only
  reconciliation after upgrade.
- Production Apply and Rollback were not performed as part of the release
  audit.
- Pairing continuity was tested only with isolated HAP test controllers.

Before a production upgrade, create a complete Home Assistant backup.
