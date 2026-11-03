# HomeKit Manager 0.10.32-rc.2

## Scope

This release candidate finalizes the native HomeKit Write/Apply and explicit
rollback path. UI↔YAML migration and experimental Home Assistant Core patches
are not part of this release candidate.

## Recovery and safety changes

- Persisted native operations use a versioned, integrity-checked operations
  journal containing a corruption-detecting SHA-256 digest over the preimage,
  target filter, fingerprints,
  revisions, authority metadata, and recovery phase.
- Startup recovery is read-only. It never retries an unknown mutation or
  performs an automatic rollback.
- A rollback reconstructed after a process restart requires a new
  process-local recovery confirmation and a newly validated write grant.
- The journal digest is unkeyed and therefore detects corruption and
  inconsistent records; it does not provide cryptographic authenticity against
  an attacker who can modify the journal and recompute the digest. Native
  writes remain independently authorized by administrator state, confirmation,
  current revisions, live filter state, locking, and a fresh write grant.
- Corrupt, unknown-version, incomplete, stale, or contradictory journal
  records remain blocked and require manual reconciliation.
- The existing Write-Grant, snapshot, confirmation, locking, fail-closed
  filtering, and Apply semantics remain in force.

## Verification

The release candidate was exercised with isolated Home Assistant Core/HAP
processes, paired test controllers, two bridges, restart recovery, explicit
rollback, and real SIGKILL fault injection. The final test matrix and the
exact temporary evidence directories are recorded in the completion report.

The production Home Assistant instance, production pairings, Config Entries,
`.storage`, native filters, and HAP persistence were not accessed or changed.
