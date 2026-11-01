# HomeKit Manager 0.10.22 – Full-Core HAP Mutation Security

Status: experimental security validation only. Native UI↔YAML migration remains
disabled in the production integration.

## Scope

The 0.10.22 campaign mutates only fresh temporary Home Assistant state after a
real two-bridge pairing and a real Core-process SIGKILL. The verification phase
starts a new Home Assistant Core process and uses the original aiohomekit
controller data; it never repairs or re-pairs a bridge.

The campaign covers both directions:

- `SOURCE_USER → SOURCE_IMPORT`
- `SOURCE_IMPORT → SOURCE_USER`

For Bridge A, the following persisted or structural mutations are injected:

- HAP MAC replacement;
- loss of all persisted controller pairings;
- AID allocation mutation;
- explicit allowlist expansion;
- duplicate Config Entry with the same bridge name and port.

Bridge B is an independently paired control bridge and is never mutated.

## Core safety boundary

The experimental Core now captures non-secret pairing and accessory-structure
fingerprints during durable prepare. On restart, the HAP driver loads persisted
state and constructs the in-memory accessory graph, but the bridge is rejected
before `_async_register_bridge()` and `driver.async_start()` when the transaction
identity, pairing fingerprint, accessory hash, allowlist, source, or Config Entry
does not match.

An identified damaged transaction becomes `MANUAL_RECOVERY_REQUIRED`. The
decision is scoped to the affected Entry. A different HomeKit Entry with a
different identity may continue to start. An unreadable journal without a
trusted identity remains globally conservative at the YAML reconciliation
boundary.

Pairing secrets and private bridge keys are not copied into the transaction
journal or test evidence. Only SHA-256 fingerprints and non-secret status data
are recorded.

## Evidence

The real Full-Core campaign passed 11/11 tests:

```text
11 passed, 1 warning in 156.96s
```

The existing multi-bridge SIGKILL regression passed 7/7 tests:

```text
7 passed, 1 warning in 31.15s
```

The HAP mutation campaign asserts all of the following for every case:

- journal state is `MANUAL_RECOVERY_REQUIRED`;
- no successful commit or rollback is recorded;
- Bridge A cannot reconnect through the original controller;
- Bridge B reconnects through its original controller;
- Bridge B's HAP state fingerprint is byte-stable;
- no additional active bridge is allowed for the duplicate-identity case;
- the process really crashed with `SIGKILL` after source mutation.

These are local `TEST VERIFIED` results. They are not a production release
approval and are not `CI VERIFIED` until the corresponding GitHub Actions run
has completed.
