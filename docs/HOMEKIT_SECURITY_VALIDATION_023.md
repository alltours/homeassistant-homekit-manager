# HomeKit Manager 0.10.23 – Security Validation

## Scope

This audit evaluates the experimental Core-owned HomeKit source-migration protocol on the verified Home Assistant Core 2026.10.4 prototype. Production native migration remains disabled.

Evidence labels are strict: `CODE VERIFIED` means the checked-out code supports the claim; `TEST VERIFIED` means a test actually ran and passed; `CI VERIFIED` is reserved for a successful GitHub Actions job; `NOT VERIFIED`, `BLOCKED`, and `FAILED` are not success states.

## Starting evidence

* Manager base: `f90a2a48ccd1708705b05a502d9aff7fb4f04bd7` (`CODE VERIFIED`).
* Core base prototype: `a4ee64492c9e6d58ed58bf23e7eeccf58c382aba` (`CODE VERIFIED`).
* 0.10.22 workflow `41258246946`: completed with failure; quality, browser, and beta jobs passed, but `experimental-core-native` failed in the migration-suite step (`CI VERIFIED` for those individual successful jobs, `FAILED` for the experimental gate).
* HACS/Hassfest workflow `41258246938`: completed successfully (`CI VERIFIED` for that workflow).
* Artifact metadata was visible, but unauthenticated archive download returned HTTP 401; artifact contents are `NOT VERIFIED`.

## Tested security boundary

The Core checks the durable migration request before HAP registration and driver start. For bridge-scoped identity mutations, Bridge A is rejected and Bridge B remains usable. A journal or snapshot with no trustworthy bridge identity is handled conservatively and may block all native YAML publication. This is an availability trade-off, not an identity bypass.

The new 0.10.23 test exercises a real Core process, real aiohomekit pairings, a SIGKILL at `AFTER_ROLLBACK_SOURCE_MUTATION`, post-crash mutation of isolated Bridge A persistence, normal Core restart, and independent reconnect checks. The Core fault injector now writes a test-only reachability marker immediately before SIGKILL (`CODE VERIFIED`; full matrix status is recorded in the final report).

The corrected rollback mutation matrix ran as 14 tests: `14 passed` in `413.83s` (`TEST VERIFIED`). It covered MAC, pairing, AID/IID allocation, allowlist, duplicate entry, journal identity, and baseline-fingerprint mutations in both migration directions. The existing persistence-fault suite then ran with `8 passed` after its corrupt-journal observer was corrected (`TEST VERIFIED`).

## Findings

1. Cross-store atomicity is not achievable with the current Config Entry, YAML, journal, and HAP stores (`OPEN`, HIGH). The protocol is crash-consistent by validation and fail-closed decisions, not an atomic multi-file commit.
2. Rollback still uses private Config Entries store methods for immediate persistence (`OPEN`, HIGH). The experimental public `async_update_entry_source` boundary reduces one coupling point but does not remove forced-store coupling.
3. A corrupt journal without a trustworthy identity can block unrelated YAML bridges (`OPEN`, MEDIUM). This is conservative and safer than guessing, but not ideal isolation.
4. Physical power-loss and real OS-level ENOSPC/EIO/EACCES guarantees remain unverified (`OPEN`, MEDIUM). Existing controlled OSError injection is not a power-failure proof.
5. The 0.10.22 experimental CI gate failed in the migration suite; a green overall release-quality workflow must not be claimed (`FAILED`).

## Decision

The stable Manager without native source migration is suitable for continued release preparation subject to its ordinary regression gates. The native migration remains an experimental lab feature and is not approved for production. Long-term support requires a small official Home Assistant Core transaction/recovery API; adding more custom-integration workarounds would increase update risk without creating cross-store atomicity.
