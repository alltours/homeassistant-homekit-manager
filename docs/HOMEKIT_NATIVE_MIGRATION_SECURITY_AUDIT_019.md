# HomeKit Manager 0.10.19 – Independent Security and Architecture Audit

## Scope and evidence boundary

This audit was performed against the requested starting commits, not against a
README or an earlier completion report:

| Repository | Requested ref | Verified ref | Result |
|---|---|---|---|
| Manager | `feature/homekit-manager-0.10.18-core-rollback` / `0818ff5f05d0d330483a61855c9d611803514003` | exact commit exists; audit branch created from it | CODE VERIFIED |
| Core prototype | `hkm-native-migration-poc-2026.10.4-0.10.18` / `5a7b4ef42cda1b79ec5855be5f365d4d647b35c4` | exact commit exists; audit branch created from it | CODE VERIFIED |

No productive Home Assistant instance, bridge, pairing, YAML file, or HAP
store was accessed. All Full-Core tests used fresh temporary configuration
directories and loopback ports. No official Core remote was modified.

The audit distinguishes code inspection from execution:

- `CODE VERIFIED`: directly established from source or a committed diff.
- `TEST VERIFIED`: executed locally and passed.
- `CI VERIFIED`: not available in this audit; no GitHub CI result is claimed.
- `NOT VERIFIED`: not executed or not provable with the available environment.
- `BLOCKED`: deliberately stopped by a safety gate or technical prerequisite.
- `FAILED`: executed and failed.

## Architecture reconstructed from source

The experimental protocol is Core-owned in
`homeassistant/components/homekit/migration.py`. The Manager adapter in
`custom_components/homekit_manager/core_migration.py` only discovers an exact
experimental API and remains fail-closed with `migration_enabled: false`.
The native production route therefore does not activate the protocol.

The Core setup path is:

1. `homekit.async_setup()` initializes the loader and services.
2. It calls `async_recover_before_yaml_reconciliation()` before
   `_async_update_entries_from_yaml()`.
3. The observation filters only the YAML candidates associated with the
   transaction; the native importer then matches by name **or** port in
   `_async_update_config_entry_from_yaml()`.
4. Config entries are set up by `async_setup_entry()`.
5. HAP starts from the `async_at_started()` callback.
6. `async_finalize_after_setup()` or `async_finalize_after_rollback()` performs
   the final identity check and persists the terminal state.

Relevant source evidence: Core `homeassistant/components/homekit/__init__.py`
lines 304–323, 327–356 and 359–431; Core
`homeassistant/components/homekit/migration.py` lines 127–171, 670–805 and
808–842; Manager `custom_components/homekit_manager/core_migration.py` lines
16–61 and 64–140.

The protocol has a forward-only state graph. `COMMITTED`, `ROLLED_BACK` and
`MANUAL_RECOVERY_REQUIRED` are terminal. This correctly prevents automatic
rollback of a durable commit, but it does not create a cross-store atomic
transaction: Config Entries, YAML and HAP persistence remain separate stores.

## Persistence and durability audit

| Store | Owner | Observed write path | Local guarantee | Cross-store guarantee |
|---|---|---|---|---|
| `homekit.migration` | Core protocol | HA `Store(..., atomic_writes=True)` | atomic serialized replacement; HA writer uses temp-file flush/fsync and directory sync | none |
| `core.config_entries` | HA Config Entries | private Core store through the experimental executor | depends on HA Store and call ordering | none |
| YAML/includes | HA configuration / user filesystem | native YAML loader or Manager writer outside this protocol | format/filesystem dependent | none |
| HAP persistence | HomeKit/pyhap | HomeKit driver persistence | runtime-specific; not part of the migration journal | none |
| pairing data | HAP controller/bridge | HAP persistence and controller state | tested in isolated reconnect scenarios | none |
| lock | protocol/harness | bridge-specific process lock | prevents selected concurrent local operations | does not serialize arbitrary Core or external writers |

The protocol documentation itself correctly states that atomic journal writes do
not make Config Entry, YAML and HAP persistence one transaction. A real power
loss window between independent stores remains `NOT VERIFIED`; a SIGKILL test is
not a physical power-failure test.

The strict loader intentionally does not treat corrupt journal data as a
missing journal. This is correct fail-closed behavior. The audit found and
fixed the previous path-check race by reading via one descriptor with
`O_NOFOLLOW` where available, `fstat()` and a hardlink-count check.

## Findings

### HKM-019-001 – stale same-port YAML could escape quarantine

- Severity: HIGH
- Status: FIXED
- Evidence: CODE VERIFIED and TEST VERIFIED
- Original cause: `_matching_yaml_indices()` required both name and port,
  while the native importer associates entries by name **or** port.
- Reproduction: change a pending bridge's YAML name while keeping its port;
  the old recovery relation returned no candidate and native reconciliation
  could create a second import entry.
- Fix: candidate matching now mirrors native importer semantics and a unit test
  covers a renamed same-port stale bridge.
- Remaining risk: multiple entries sharing either identity attribute are still
  correctly treated as ambiguous and require manual recovery.

### HKM-019-002 – baseline and target payloads were not fully bound to revisions

- Severity: HIGH
- Status: FIXED
- Evidence: CODE VERIFIED and TEST VERIFIED
- Original cause: persisted `baseline_data`/`baseline_options` and target
  payloads were accepted without recomputing the corresponding fingerprints.
- Reproduction: alter rollback data or target options while leaving the stored
  revision unchanged.
- Fix: `_normalise_request()` recomputes and validates baseline and target
  fingerprints; partial baseline records are rejected.
- Remaining risk: this protects the journal envelope, not external stores that
  change after validation; revision checks still have a TOCTOU boundary.

### HKM-019-003 – journal symlink/hardlink validation had a TOCTOU window

- Severity: HIGH
- Status: FIXED
- Evidence: CODE VERIFIED and TEST VERIFIED for static cases
- Original cause: separate `stat()`, `is_symlink()` and `read_text()` calls.
- Fix: one descriptor is opened and checked with `fstat()` before reading;
  symlinks are rejected by `O_NOFOLLOW` where supported and hardlinks by
  `st_nlink != 1`.
- Remaining risk: a hostile filesystem or platform with weaker open flags is
  not fully exercised by a race stress test.

### HKM-019-004 – no atomic commit spans all persistence systems

- Severity: HIGH
- Status: OPEN / architectural limitation
- Evidence: CODE VERIFIED; crash-window power-loss behavior is NOT VERIFIED.
- Impact: a journal can durably say `COMMIT_PENDING` while a separate YAML,
  Config Entry or HAP write has a different durability outcome. The protocol
  can fail closed or recover from known states, but it cannot claim a true
  atomic multi-store commit.
- Recommendation: retain Core ownership, make every external state a verified
  precondition/postcondition, and keep ambiguous states blocked. A true
  transaction would require a Core contract covering all affected stores.

### HKM-019-005 – private Core internals are used by the experiment

- Severity: HIGH
- Status: OPEN
- Evidence: CODE VERIFIED in the rollback executor (`ConfigEntries._store` and
  `_data_to_save`).
- Impact: cache/store divergence, listener bypass, and breakage on Core updates
  are possible. This is not an upstream-ready public API.
- Recommendation: upstream a small HomeKit-specific transaction boundary; the
  Manager must not mutate `ConfigEntry.source` or Core stores directly.

### HKM-019-006 – global journal scope limits availability isolation

- Severity: MEDIUM
- Status: OPEN
- Evidence: CODE VERIFIED. No foreign-bridge mutation was observed.
- Impact: an unreadable or identity-ambiguous global journal blocks all native
  YAML reconciliation because no transaction can safely be attributed. This is
  conservative availability loss, not a demonstrated cross-bridge write.
- Recommendation: per-bridge journals plus a signed/strict persistent index;
  retain global blocking when identity cannot be established.

### HKM-019-007 – integration harness is not safe for parallel suites

- Severity: MEDIUM
- Status: OPEN test-infrastructure issue
- Evidence: TEST VERIFIED during a concurrent run: subprocesses collided on
  HTTP port 8123 and produced `address already in use` / `not_loaded` failures.
- Recommendation: serialize Full-Core suites or assign a unique HTTP port to
  every subprocess and fixture.

### HKM-019-008 – pairing fingerprint assertion was missing in the multibridge worker

- Severity: MEDIUM
- Status: FIXED
- Evidence: CODE VERIFIED and TEST VERIFIED
- Original gap: reconnect verified HAP accessories and AIDs but not the stored
  pairing-data fingerprint.
- Fix: `_reconnect()` now asserts the pairing fingerprint in a `try/finally`
  lifecycle.
- Remaining risk: this is a stronger test assertion, not proof of Apple Home
  scenes, room assignments, or a physical controller.

### HKM-019-009 – physical filesystem/power-failure guarantees remain unverified

- Severity: MEDIUM
- Status: OPEN
- Evidence: CODE VERIFIED; controlled exceptions and SIGKILL are not physical
  ENOSPC/EIO/power-loss tests.
- Recommendation: use a disposable filesystem/VM fault harness before any
  production claim.

### HKM-019-010 – browser backend E2E currently fails

- Severity: MEDIUM
- Status: FAILED / open
- Evidence: TEST VERIFIED as a failure: Chromium and WebKit backend tests hit
  the Node assertion at `tests/frontend/backend_e2e.mjs:15` (`false !== true`).
- Impact: browser/backend behavior is not fully release-verified by this audit.
- Recommendation: isolate the frontend backend failure and rerun both browser
  engines after fixing the fixture or implementation.

### HKM-019-011 – production exposure is disabled

- Severity: INFORMATIONAL
- Status: CODE VERIFIED
- Evidence: Manager capability returns `migration_enabled: false`; README and
  adapter documentation state that native source mutation is experimental.
- Impact: the audit findings do not imply a production migration was executed.

## Adversarial scenario matrix

| Scenario | Expected safe behavior | Audit result |
|---|---|---|
| crash after journal rename / before directory sync | strict load or manual block; no guessed state | CODE VERIFIED store contract; physical crash NOT VERIFIED |
| delayed Config Entry persistence | do not mark commit without postcondition | CODE VERIFIED; external delay NOT VERIFIED |
| YAML changed during migration | revision/conflict block | CODE VERIFIED; race timing NOT VERIFIED |
| concurrent migrations | one transaction wins; other blocks | NOT VERIFIED as a true multi-process race |
| wrong bridge ID | reject or global/manual block | TEST VERIFIED at envelope/identity validation level |
| old snapshot | reject fingerprint/transaction mismatch | TEST VERIFIED for payload mismatch; full stale-file run NOT VERIFIED |
| rollback/commit race | terminal commit cannot be reopened | CODE VERIFIED; true concurrent race NOT VERIFIED |
| HAP setup with changed structure | signature and AID/IID checks must fail | CODE VERIFIED in harness; mutation negative control NOT VERIFIED |
| recovery invoked twice | idempotent terminal behavior | TEST VERIFIED in existing protocol/rollback suites |
| same-port renamed stale YAML | quarantine candidate, no duplicate | TEST VERIFIED after fix |
| journal symlink/hardlink swap | reject unsafe file | CODE VERIFIED; static checks TEST VERIFIED, stress race NOT VERIFIED |

## Test-validity audit

The Full-Core worker starts an actual Home Assistant process phase, creates
actual HomeKit entries and uses `aiohomekit` pairing/reconnect. It compares
accessory service/characteristic signatures, AIDs, and now pairing-data
fingerprints. The valid serial suites therefore provide meaningful evidence.

An important validity failure was found: running the rollback suite without the
explicit experimental Core checkout made all adapter capability checks fail
closed. This was not a migration failure, but it proved that the test command
must pin the Core checkout explicitly. A second validity issue was the fixed
HTTP port during parallel subprocess execution; those results are not counted
as functional test failures.

Negative controls executed through the Core protocol unit suite included:

1. tampered rollback baseline payload → rejected;
2. tampered target options with stale target revision → rejected;
3. renamed same-port YAML → quarantined;
4. invalid state/terminal transition → rejected by the state graph;
5. strict malformed journal envelope → manual recovery path.

The controls were restored by construction; no production or main branch was
modified. A source-code mutation that disables an assertion was not performed
on the real branches because it would not add evidence beyond the direct
negative tests and would risk contaminating the audit checkout.

## Core upstream readiness

The prototype is not upstream-ready. The smallest viable upstream contract is a
HomeKit-owned API that owns bridge identity, source switch, YAML reconciliation,
HAP lifecycle, and recovery as one Core state machine. It should expose only
validated request/prepare/commit/rollback/status operations, retain the
transaction journal in Core, and reject unknown protocol versions. It must not
accept arbitrary callbacks or trust a custom integration's journal as an
instruction stream.

The Manager can remain HACS-installable as a read-only capability adapter on
older Core versions. It should enable migration only after structural capability
checks and an explicit Core protocol version are present. No Supervisor or HA OS
change is required for the read-only Manager; a true pre-reconciliation Core
contract is required for native migration.

## Audit decision

- Experimental protocol quality: **C – substantial, test-backed prototype with
  three concrete fixes, but open cross-store and private-API risks**.
- Productive native migration: **NO-GO**.
- Upstream integration: **NO-GO for direct submission; CONDITIONAL GO for a
  separately designed Core API proposal**.

The positive isolated HAP results are credible for the scenarios actually run,
but they do not prove power-loss durability, arbitrary filesystem failures,
concurrent external writers, Apple Home scene behavior, or long-term Core API
compatibility.
