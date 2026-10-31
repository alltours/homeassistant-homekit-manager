# HomeKit Manager 0.10.19 – Findings Register

This register contains findings from the independent audit branch. Statuses are
not release claims.

| ID | Severity | Status | Component | Summary |
|---|---|---|---|---|
| HKM-019-001 | HIGH | FIXED | Core YAML quarantine | Same-port YAML with a changed name could escape recovery matching and create a duplicate import entry. |
| HKM-019-002 | HIGH | FIXED | Core journal validation | Persisted baseline/target payloads were not fully recomputed against stored revisions. |
| HKM-019-003 | HIGH | FIXED | Core journal loader | Separate path checks created a symlink/hardlink TOCTOU window. |
| HKM-019-004 | HIGH | OPEN | Cross-store protocol | Journal, Config Entries, YAML and HAP persistence have no atomic common commit. |
| HKM-019-005 | HIGH | OPEN | Core API boundary | Rollback uses private Config Entries store/data internals. |
| HKM-019-006 | MEDIUM | OPEN | Journal isolation | A global unreadable/ambiguous journal can block unrelated YAML bridges. |
| HKM-019-007 | MEDIUM | OPEN | Test harness | Concurrent suites collide on the fixed HA HTTP port 8123. |
| HKM-019-008 | MEDIUM | FIXED | HAP test validity | Multibridge reconnect did not compare pairing-data fingerprints. |
| HKM-019-009 | MEDIUM | OPEN | Fault realism | Physical power-loss and OS-level ENOSPC/EIO/EACCES evidence is incomplete. |
| HKM-019-010 | MEDIUM | OPEN | Browser E2E | Chromium and WebKit backend E2E currently fail at the Node assertion. |
| HKM-019-011 | INFORMATIONAL | CONFIRMED | Production gate | Manager native migration remains disabled and fail-closed. |

## Fixed finding details

### HKM-019-001

The Core native importer uses name **or** port to associate an existing
`SOURCE_IMPORT` entry (`homeassistant/components/homekit/__init__.py`,
`_async_update_config_entry_from_yaml`). The recovery filter previously used
name **and** port. The audit changed `_matching_yaml_indices()` to the same OR
relation and added `test_yaml_candidate_matching_covers_native_port_matching`.

### HKM-019-002

`_normalise_request()` now rejects partial baseline data and recomputes the
baseline fingerprint from entry ID, source, data and options. It also recomputes
the target revision from target data and options. Tests mutate each persisted
payload without updating its revision and assert `HomeKitMigrationError`.

### HKM-019-003

`_read_journal_text()` opens the journal once, requests `O_NOFOLLOW` and
`O_CLOEXEC` when available, uses `fstat()`, rejects a link count other than one,
and reads from the already-open descriptor. This removes the most direct
path-replacement race between validation and read. A filesystem race stress
test across all supported platforms remains open.

### HKM-019-008

The multibridge worker now compares the fingerprint of the persisted pairing
data on every reconnect, while still closing the pairing in `finally`. This
prevents a reconnect test from silently passing with a newly generated pairing
record.

## Open high-risk items

### HKM-019-004 – cross-store atomicity

The protocol is crash-consistent only to the extent that its journal can
classify observed states. It does not make a physical transaction across Core
Config Entries, arbitrary YAML files and pyhap persistence. A power loss after
one store is durable and before another is durable remains an unverified
boundary. The safe behavior must remain fail-closed; the prototype must not be
marketed as an atomic distributed transaction.

### HKM-019-005 – private API coupling

The rollback executor reaches into Core Config Entries internals. This is
acceptable only for the local prototype and is not a stable HACS/Core contract.
An upstream design must move source mutation and persistence ownership into a
public HomeKit Core API.

## Release gate interpretation

The two fixed high findings are covered by tests. The open high findings block a
productive native migration and block an upstream-ready claim. The audit branch
is therefore an engineering evidence branch, not a release branch.
