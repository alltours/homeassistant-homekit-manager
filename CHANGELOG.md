# Changelog

## 0.9.20 — local release candidate (2026-10-27)

- Separate entity-referenced device IDs from native enumerable devices, synthetic composite IDs and missing references. Expose reconciliation evidence without forcing the native UI count.
- Classify inventory entries as available, unavailable, unknown, no current state, disabled or demonstrably orphaned; show these categories in the panel.
- Make compatibility findings depend on the selected Bridge filter. Preserve unknown publication and Apple Home visibility; downgrade duplicate explicit assignments to a warning.
- Ignore identical state events and redundant HomeKit action events; count events, full recomputations, CPU time and refresh phases. Keep atomic snapshots and fetch frontend updates that arrive during an in-flight read.
- Reduce inventory projection cost by deep-copying only nested state attributes. Isolated 1,172-entity benchmark and integration/browser regressions added.
- Correct read-only source classification so a YAML-imported Config Entry is not counted as a second native source.
- Document source-specific adapter architecture, bidirectional conversion limits, pairing identity, migration risks and the decision to keep production writes disabled.
- Keep the backend apply lock and all native HomeKit state untouched. No source migration, reload or Apple Home pairing test is claimed.
# Unreleased development toward 0.9.24

- Added isolated, revisions-bound native and narrowly scoped direct-include YAML filter writers with Core 2026.10.4 integration tests. Production HomeKit application remains blocked.
- Added value-only native/YAML conversion with unknown-field rejection and repeated semantic roundtrip tests. No HAP identity or pairing migration is provided.
- Preserved mobile navigation within the 393 px viewport after the 0.9.20 GitHub browser CI finding.
- The integration version remains 0.9.20 until the 0.9.24 definition of done is proven.
