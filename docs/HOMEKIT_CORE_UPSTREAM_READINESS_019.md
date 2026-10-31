# HomeKit Native Migration – Core Upstream Readiness 0.10.19

## Decision

**NO-GO for direct upstream integration.** The prototype demonstrates a useful
HomeKit-specific pre-reconciliation boundary and a meaningful recovery protocol,
but it still depends on private Config Entry internals and has no atomic commit
contract spanning Config Entries, YAML and HAP persistence.

## Required Core contract

An upstreamable design should make Home Assistant Core the sole owner of the
critical transaction:

1. `async_prepare_homekit_source_migration(entry_id, target_source, target)`
   validates identity, source, target configuration, allowlist and Core
   capabilities, then durably records a Core-owned intent.
2. `async_begin_homekit_source_migration(transaction_id)` quiesces only the
   selected bridge and prevents native reconciliation for that identity.
3. `async_commit_homekit_source_migration(transaction_id)` performs source
   mutation, reconciliation, HAP reload and identity verification under Core
   ownership.
4. `async_rollback_homekit_source_migration(transaction_id)` is write-ahead,
   identity-bound and idempotent.
5. A pre-reconciliation callback is executed by the HomeKit integration before
   any YAML import flow can create or update an entry.
6. Status exposes only validated state and never accepts arbitrary custom
   callbacks or untrusted recovery instructions.

The contract must define which stores are covered, which durability guarantee is
made, and which ambiguous states become `MANUAL_RECOVERY_REQUIRED`. It must not
claim a multi-file atomic transaction unless Core actually supplies it.

## Manager compatibility model

The Manager can remain a HACS custom integration:

- On older Core versions, its read-only inventory and administration functions
  continue to work; native migration remains disabled.
- On a Core exposing the exact versioned contract, the Manager performs
  capability discovery and displays status/preflight information.
- Migration is fail-closed when the contract, schema, identity or allowlist
  evidence is absent.
- No Supervisor or Home Assistant OS change is necessary for the read-only
  path. Native migration requires the Core HomeKit contract, not an OS hook.

## Current blockers

1. The prototype uses private Config Entry store/data attributes.
2. The protocol cannot durably commit YAML, Config Entries and HAP persistence
   as one physical transaction.
3. A global migration journal can cause availability loss for unrelated YAML
   bridges if identity is unreadable; per-bridge records are preferable.
4. Power-loss and real OS filesystem fault evidence is not complete.
5. The browser/backend E2E suite currently fails for both Chromium and WebKit.

## Suggested upstream test contract

Core tests should assert: stable entry identity, source and port preservation,
HAP MAC and pairing continuity, AID/IID continuity, exact allowlist continuity,
no duplicate entries, unrelated-bridge isolation, repeated startup recovery,
and fail-closed behavior for corrupt journal/snapshot data. Tests must use a
fresh temporary Core directory and explicit unique HTTP/HAP ports.

No upstream Pull Request was created by this audit.
