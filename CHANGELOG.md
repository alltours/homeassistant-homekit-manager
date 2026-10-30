# Changelog

## 0.10.7 (2026-10-30)

- Detect and display mismatches between saved Manager intent and the native HomeKit filter even without local unsaved changes.
- Require an explicit positive-list migration before applying legacy domain/glob filters; preserve a safe, canonical six-key filter representation and block empty positive lists.
- Keep stored legacy exclusions separate from inferred migration intent and report native-options verification separately from runtime-publication verification.
- Add regression coverage for the confirmed exclusion gap, migration ambiguity, filter safety and rollback verification. No productive HomeKit change is included.

## 0.10.6 (2026-10-30)

- Condense closed area and device cards while retaining two visible draft-only bulk actions and the separate aggregate status.
- Move display options and secondary inventory counts into the collapsed filter panel; preserve choices and open detail state on passive refresh.
- Simplify the HomeKit overview and empty Changes view; retain positive-list, active test-mode and uncertain-operation warnings.
- Keep source, writer authority and diagnostics in reachable technical details and Settings. No HomeKit filter, pairing or writer behavior changes.

## 0.10.5 (2026-10-29)

- Calculate complete device and area bulk scopes on the server, excluding disabled, hidden, technical, missing-state, missing-registry, unsupported and unverified entities by default. A forged draft cannot newly include these entities through the filter planner.
- Show actual changed, unchanged and skipped counts with reasons before a bulk action changes the Manager draft. Zero-change actions leave the draft untouched.
- Show real device-less entities directly under their area; simplify names, aggregate status and mobile controls while retaining technical facts in details.
- Keep display-option checkboxes compact with full-width touch labels at phone widths.
- Correct the filter-reason API/UI field mismatch and add version-gated compatibility projection for Core 2026.11.0b0. Unknown future versions remain unverified.
- Retain filter-only, operation-bound production authorization, exact revision checks, source binding and no automatic retry. No productive installation or HomeKit change is part of this release.

## 0.10.4 (2026-10-29)

- Published the documentation-only UX target and prioritized roadmap for separate, directly visible device and area bulk-action buttons.
- Documented the proposed default exclusions and detailed confirmation counts for unsupported, hidden, categorized and disabled entities. These are future work, not behavior added in 0.10.4.
- Updated release metadata to 0.10.4. HomeKit filter writers, authorization, pairing and runtime behavior remain unchanged from 0.10.3.

## 0.10.3 (2026-10-29)

- Added the area → device → entity hierarchy. Device placement uses the actual device area while entity overrides remain visible as entity metadata.
- Added explicit include/exclude actions on areas and devices. Confirmation shows full-scope counts even when search, filters or pagination hide members; all actions remain draft-only.
- Added current and planned aggregate filter status, keyboard and responsive browser coverage, and a 5,000-entity bulk-action test.
- Count only actual entity filter changes in a server-side operation plan when a saved draft also contains no-op overrides; block all-no-op plans.
- Keep expanded entity and bridge technical details open across passive inventory refreshes.
- Show a neutral "Keine Anwendung protokolliert" state when no apply operation exists; reserve "Ergebnis unbekannt" for an actual operation with uncertain outcome.

## 0.10.2 (2026-10-29)

- Kept native device-filter and diagnostic dropdown controls mounted while passive inventory updates arrive; a pending view update renders after selection or focus leaves the control.
- Restored focus after a deliberate dropdown selection. Added Chromium, WebKit and mobile-touch regression coverage for refresh, waiting, selection, keyboard navigation and outside clicks.
- Retained the 0.10.1 native filter test mode and its server-side authorization boundaries without change.

## 0.10.1 (2026-10-29)

- Added a separately confirmed, one-hour in-memory test mode for one existing native `SOURCE_USER` HomeKit Bridge on Core 2026.10.4. It starts disabled, requires Admin access, expires or is revoked without a local grant file, and does not authorize YAML or accessory writes.
- Preserved filter-only planning, exact Entry revision checks, Core schema validation, operation journaling, duplicate rejection and read-only reconciliation. The Apply confirmation now names the concrete entity diff.
- Productive installation and the first Apply remain separate approvals; this development change has not been installed on the existing Home Assistant system.
- Verified the native filter-only writer on isolated Core 2026.11.0b0 with the four requested sensor exclusions, Core reload, persisted options, and a paired loopback HAP controller reconnecting after a full Core restart. YAML writing and general accessory mapping remain at their previous limits. The productive Core is 2026.11.0b0, but its backup inventory currently reports no available backups; installation is blocked pending backup verification.

## 0.10.0 (2026-10-28)

- Matched the six Core 2026.10.4 filter cases and HomeKit's hidden/category gate against the installed Core implementation.
- Blocked entity-list edits that would change the default selection of unobserved entities.
- Restricted the isolated native writer to Core-validated filter lists; forged or unsupported option diffs are rejected before touching a Config Entry.
- Separated missing device references from current State availability, and aligned UI status counts with active search and filters.
- Removed the misleading management-surface switch from the panel. It changed only Manager metadata and never authorized HomeKit writes; the UI now presents the actual source and server-side write status.
- Kept Core filter selection separate from the later hidden/category registry gate and its runtime candidacy; the panel shows both pieces of evidence.
- Runtime candidacy now also requires a current State-machine entry; unknown State evidence stays unknown instead of implying publication.
- Bounded inventory WebSocket responses to 500 entities per page after a 5,000-entity response exceeded the 4-MiB test-client limit. The panel now assembles only matching snapshot revisions and declines partial results; arbitrary State attributes stay server-side.
- Bounded device and area WebSocket responses after a 5,000-device inventory context also exceeded the client limit. The panel groups its complete paged inventory locally.
- Added isolated direct `configuration.yaml` HomeKit filter editing with byte-preserving plans, backups, Core import/reload tests and inode-swap refusal. Mixed native/YAML installations remain read-only for YAML apply.
- Blocked YAML replacement for read-only or shared-writable sources and for extended attributes that cannot be preserved; normal macOS provenance metadata remains supported.
- Verified that corrupted YAML backups and inode swaps during restore fail without replacing the current source.
- Added a local, entry-bound, source-bound and maximum 24-hour filter grant for a later controlled production apply. Missing, revoked, expired, symlinked or overly permissive grants fail closed. The existing production installation was not changed or authorized.
- Closed grant-revocation races while a native apply waits for its bridge lock or a YAML apply waits for an executor worker; both writers recheck immediately before their mutation.
- Verified YAML Core reload with a loopback HAP testcontroller pairing and stable MAC/AID/IIDs, in addition to the native loopback test. Physical Apple Home remains untested.
- Reconnected an isolated HAP testcontroller across two fresh Python interpreters. The second Core harness loads the test Config Entry from its temporary `.storage/core.config_entries` file and uses the same temporary HAP storage. This is distinct from a full Home Assistant service restart.
- Verified a separate two-process full Home Assistant bootstrap: Core auto-loaded a persisted native HomeKit Config Entry, and a loopback HAP controller reconnected with unchanged MAC, AID and IIDs. No physical Apple Home device was involved.
- Closed HAP discovery sessions after pairing in the isolated tests, including failure paths, so reconnect tasks do not survive test teardown.
- Rechecked the complete native Config Entry revision under the bridge lock immediately before mutation; unrelated concurrent option changes now block apply.
- Rechecked the YAML grant immediately before atomic source replacement, and rejected unsafe backup-directory permissions and hardlinked journals.
- Rejected macOS extended ACLs on write grants, writable YAML source files, backup directories and journals; mode bits alone do not capture these permissions.
- The full Python dependency audit remains visible in CI. Its 39 reviewed Pillow 12.3.0 findings are documented as a Core platform risk outside the Manager's Bridge-filter path; a new advisory, changed Core pin or Manager Pillow import fails the gate. The Core platform risk remains until a compatible patched Core version is tested.
- Restricted all filter planning and writing boundaries to HomeKit Bridge mode. Accessory-mode entries, including cameras, remain read-only even through direct adapter calls.
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
