# Changelog

## Unreleased — 0.10.0 development (NO-GO)

- Matched the six Core 2026.10.4 filter cases and HomeKit's hidden/category gate against the installed Core implementation.
- Blocked entity-list edits that would change the default selection of unobserved entities.
- Restricted the isolated native writer to Core-validated filter lists; forged or unsupported option diffs are rejected before touching a Config Entry.
- Separated missing device references from current State availability, and aligned UI status counts with active search and filters.
- Kept Core filter selection separate from the later hidden/category registry gate and its runtime candidacy; the panel shows both pieces of evidence.
- Runtime candidacy now also requires a current State-machine entry; unknown State evidence stays unknown instead of implying publication.
- Bounded inventory WebSocket responses to 500 entities per page after a 5,000-entity response exceeded the 4-MiB test-client limit. The panel now assembles only matching snapshot revisions and declines partial results; arbitrary State attributes stay server-side.
- Added isolated direct `configuration.yaml` HomeKit filter editing with byte-preserving plans, backups, Core import/reload tests and inode-swap refusal. Mixed native/YAML installations remain read-only for YAML apply.
- Blocked YAML replacement for read-only or shared-writable sources and for extended attributes that cannot be preserved; normal macOS provenance metadata remains supported.
- Verified that corrupted YAML backups and inode swaps during restore fail without replacing the current source.
- Added a local, entry-bound, source-bound and maximum 24-hour filter grant for a later controlled production apply. Missing, revoked, expired, symlinked or overly permissive grants fail closed. The existing production installation was not changed or authorized.
- Verified YAML Core reload with a loopback HAP testcontroller pairing and stable MAC/AID/IIDs, in addition to the native loopback test. A full HA process restart and physical Apple Home remain untested.
- Reconnected an isolated HAP testcontroller across two fresh Python interpreters using the same temporary Core/HAP storage and fixed test Entry-ID; this is distinct from a full Home Assistant service restart with persisted Config Entry loading.
- Exercised all 32 WebSocket routes with an authenticated non-admin account; every route rejected the request.
- Added an isolated Core/HAP driver test for MAC and AID/IID stability across a filter options reload; network advertisement and pairing remain untested.
- Paired an isolated `aiohomekit` controller to the real HAP TCP server on loopback; it reconnected after a Core options reload and observed stable AID/IIDs loaded from real temporary storage files. mDNS was replaced by a test advertiser; Apple Home remains untested.
- Recorded verified baseline evidence, exact capability limits and remaining release gates in `docs/DEVELOPMENT_0_10_0.md`. Production writing on the existing installation remains disabled.
- Added a fresh extraction check for release archive structure, Python syntax and JSON validity; the final 0.10.0 archive still requires its own check.

## 0.9.24 (2026-10-27)

- Preserved native `SOURCE_USER` and YAML `SOURCE_IMPORT` as separate authoritative sources and retired all YAML↔UI source-migration actions for 0.9.24 and 0.10.0.
- Added source-bound internal snapshots, a unified Changes workflow and an expandable, redacted Config Entry data/options view.
- Added isolated, revisions-bound native and narrowly scoped direct-include YAML filter writers with real Core 2026.10.4 and authenticated WebSocket integration tests. Production HomeKit application remains blocked.
- Persisted operation metadata for duplicate request rejection and read-only reconciliation; added YAML metadata journal, verified backup/restore tests and concurrent-apply reconciliation protection.
- Added internal native/YAML value projections with unknown-field rejection and semantic roundtrip tests. No HAP identity or pairing migration is provided.
- Redacted lock and alarm code fields from bridge data returned to the UI.
- Added dependency, tracked-file and mobile browser CI checks.

## 0.9.20 — local release candidate (2026-10-27)

- Separate entity-referenced device IDs from native enumerable devices, synthetic composite IDs and missing references. Expose reconciliation evidence without forcing the native UI count.
- Classify inventory entries as available, unavailable, unknown, no current state, disabled or demonstrably orphaned; show these categories in the panel.
- Make compatibility findings depend on the selected Bridge filter. Preserve unknown publication and Apple Home visibility; downgrade duplicate explicit assignments to a warning.
- Ignore identical state events and redundant HomeKit action events; count events, full recomputations, CPU time and refresh phases. Keep atomic snapshots and fetch frontend updates that arrive during an in-flight read.
- Reduce inventory projection cost by deep-copying only nested state attributes. Isolated 1,172-entity benchmark and integration/browser regressions added.
- Correct read-only source classification so a YAML-imported Config Entry is not counted as a second native source.
- Document source-specific adapter architecture, bidirectional conversion limits, pairing identity, migration risks and the decision to keep production writes disabled.
- Keep the backend apply lock and all native HomeKit state untouched. No source migration, reload or Apple Home pairing test is claimed.
