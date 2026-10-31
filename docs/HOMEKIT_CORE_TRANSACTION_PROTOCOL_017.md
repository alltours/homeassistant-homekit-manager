# HomeKit Core Transaction Protocol 0.10.17

## Scope

This document describes the experimental Core-owned protocol used by the
0.10.17 prototype. It is not a public Home Assistant API and does not enable
native source migration in the released Manager integration.

## Ownership

Home Assistant Core owns the transaction journal, source mutation, startup
recovery decision and final commit marker. HomeKit Manager may submit a
validated migration request and read status, but it cannot mark a transaction
committed or override a Core recovery decision.

## Persistent request fields

Each v2 request contains:

- `transaction_id`, `entry_id`, source and target source;
- baseline and target revisions;
- positive-list fingerprint;
- non-secret HAP identity fingerprint containing entry ID, bridge MAC, name and
  port;
- protocol version, state, commit status and recovery generation;
- target data/options and the redacted allowlist.

Pairing secrets and controller credentials are never stored in the request.

The Core journal is written through Home Assistant's `Store` with
`atomic_writes=True`; the underlying atomic writer fsyncs the temporary file
before replacement. Config-entry storage, YAML and HAP persistence remain
separate stores and therefore are verified independently rather than being
presented as one physical transaction.

## State transitions

The protocol uses the following forward-only states:

`PREPARING → PREPARED → SOURCE_SWITCH_PENDING → SOURCE_SWITCHED → VERIFYING → COMMIT_PENDING → COMMITTED`

`RECONCILING` and `RELOADING` are valid intermediate states for a future Core
reload implementation. Rollback uses:

`ROLLBACK_PENDING → ROLLING_BACK → ROLLED_BACK`

Any uncertainty transitions to `MANUAL_RECOVERY_REQUIRED`. Terminal states are
not reopened. Invalid transitions are rejected before persistence.

## Commit contract

`COMMITTED` is written only after:

1. the target Config Entry source and target data/options are persisted;
2. the target allowlist matches its fingerprint;
3. the HAP bridge has started;
4. the observed bridge MAC matches the baseline;
5. the transaction is first persisted as `COMMIT_PENDING`.

The protocol does not claim an atomic transaction across YAML, Config Entry
storage and HAP persistence. The Core boundary instead guarantees deterministic
recovery or explicit blocking when that cross-store guarantee is unavailable.

## Startup recovery

Recovery reads the journal before native YAML reconciliation. It compares the
persisted entry, target configuration and allowlist against the request. A
target-side match enters `VERIFYING`; an origin-side match without an
unambiguous reversible operation is blocked. A corrupt or identity-inconsistent
journal is never replaced and blocks the affected YAML reconciliation path.

## Proposed upstream contract

A future public HomeKit Core API should expose:

- `async_prepare_source_migration(request) -> transaction_id`;
- `async_get_source_migration_status(transaction_id)`;
- `async_commit_source_migration(transaction_id, verification)`;
- `async_rollback_source_migration(transaction_id)`;
- a pre-YAML-reconciliation recovery hook owned by the HomeKit integration.

The API must document source persistence, unload/reload behavior, HAP identity
guarantees, failure states and the exact meaning of commit. Supervisor and OS
changes should not be required. Older Core versions must fail closed and retain
the existing read-only Manager behavior.
