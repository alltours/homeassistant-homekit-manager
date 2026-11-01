# HomeKit Manager 0.10.23 – Filesystem Fault Injection

## Scope and terminology

The persistence tests distinguish controlled Python exceptions from operating-system failures. `OSError(ENOSPC|EIO|EACCES)` raised by the isolated Core fault adapter is a simulated I/O failure. SIGKILL is a process-abort test. No test in this audit is a physical power-loss test, VM crash test, or proof of storage-controller durability.

## Persistence matrix

| Store | Owner | Boundary | Current evidence | Recovery consequence |
|---|---|---|---|---|
| `.storage/core.config_entries` | Home Assistant Core | Core ConfigEntryStore forced save through private `_store`/`_data_to_save` | `CODE VERIFIED`; atomic store behavior is inherited, cross-store atomicity is not | mismatch => manual block |
| `.storage/homekit.migration` | patched HomeKit Core | `Store(..., atomic_writes=True)` plus strict envelope read | `CODE VERIFIED`; journal corruption is distinguished from missing journal | unknown/corrupt => fail closed |
| YAML and includes | HA YAML loader / filesystem | file mutation and native reconciliation | `CODE VERIFIED`; external conflict checks exist | ambiguous source => block |
| HAP state/AID files | HomeKit/pyhap | driver persistence | real HAP mutation tests exist | identity/pairing/accessory mismatch => no publish |
| Manager journal/snapshots | Custom integration | separate read-only metadata | not the authority for Core transaction decisions | never authorizes native mutation |

## Fault classes

* Controlled `ENOSPC`, `EIO`, and `EACCES`: `TEST VERIFIED` where covered by the existing 0.10.16 persistence tests; these are simulated exceptions.
* Partial/truncated/invalid journal and snapshot: `TEST VERIFIED` for strict validation paths where the existing tests execute; physical torn-write behavior is `NOT VERIFIED`.
* Atomic rename and file fsync: `CODE VERIFIED` only to the extent guaranteed by Home Assistant's atomic Store implementation; directory-fsync and storage-device power-loss semantics are `NOT VERIFIED`.
* Real loopback filesystem exhaustion or I/O fault: `NOT VERIFIED` in this environment.

## Security rule

No simulated persistence error may produce `COMMITTED` or `ROLLED_BACK` without the corresponding identity and configuration verification. If the evidence cannot determine the bridge or baseline, the only acceptable result is `MANUAL_RECOVERY_REQUIRED`.
