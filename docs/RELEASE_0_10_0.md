# HomeKit Manager 0.10.0 — Release Notes

Version 0.10.0 supports **Home Assistant Core 2026.10.4**. It manages existing HomeKit Bridges in one four-tab panel while retaining each Bridge's original `SOURCE_USER` or `SOURCE_IMPORT` configuration source. It never migrates YAML to UI or UI to YAML, creates a replacement Bridge, or resets a pairing.

## Supported operations

| Source and structure | Read / draft / preview | Filter apply | Boundary |
|---|---|---|---|
| Native `SOURCE_USER`, Bridge mode | Yes | Yes, with local grant | HomeKit filter lists only; all other Entry fields remain unchanged. |
| YAML `SOURCE_IMPORT`, direct `homekit:` or one direct `!include`, Bridge mode | Yes | Yes, with local grant | Only unambiguous, byte-roundtrippable plain structures, safe file metadata and all-import HomeKit installations. |
| Mixed native and YAML installation | Yes | Native only | YAML reload would also reload native Entries on Core 2026.10.4. |
| Packages, `!include_dir_*`, nested includes, tags, secrets, anchors, aliases, ambiguous identity or unsafe file metadata | Yes where Core can read them | No | Provenance, formatting or safe replacement cannot be proven. |
| Accessory mode including camera | Listed separately | No | Bridge filter writer does not manage Accessory identity or camera streams. |
| Other Core version | Read with unknown compatibility | No | Writer contract is version-pinned. |

Apply is disabled by default. A Home Assistant administrator must explicitly confirm the planned operation, and a separate local grant, limited to one Entry, source, filter scope, Core version and at most 24 hours, must be present. The UI cannot create a grant. The existing productive Bridge received no grant. Backup, journal, post-write verification and read-only reconciliation are implemented; failed or uncertain outcomes are never retried automatically.

## Changes since 0.9.24

- Core 2026.10.4 filter rules, hidden/category handling, inventory status and HomeKit compatibility are distinguished from actual HAP publication and Apple Home visibility.
- Entity and device inventory is paginated in 500-entry snapshots; search, filter, sort and multi-selection work across pages. The four main tabs remain HomeKit, Devices, Changes and Settings.
- Native and simple YAML Bridge filter writers are isolated by source, validated against Core and protected by revisions, bridge-scoped locks and a revocable local grant.
- Direct and directly included YAML edits retain unchanged source bytes and use atomic replacement, private backup, provenance, metadata and ACL checks. Unsafe structures remain read-only.
- Isolated Home Assistant/Core HAP tests use a loopback `aiohomekit` controller and verify reconnect plus MAC/AID/IID stability across filter reload and a two-process Core restart. These are **not** physical Apple Home tests.
- The full Python runtime dependency audit remains visible. The [Pillow 12.3.0 platform risk decision](SECURITY_PYTHON_DEPENDENCIES_0_10_0.md) accepts only the 39 individually reviewed IDs for the exact Core pin; any other or new finding fails CI.

## Known limits and safety

- No physical Apple Home pairing persistence test and no productive Bridge apply were performed. A testcontroller's HAP reconnect does not prove Apple Home UI visibility.
- Core 2026.10.4 pins Pillow 12.3.0 with 39 known security advisories fixed in Pillow 13.0.0. HomeKit Manager does not invoke their image-processing paths for the supported Bridge filter operation, but other Core integrations may. A future patched Core version needs its own compatibility run.
- The currently installed productive Core/Manager versions and the reported 1,216 / 375 / 251 entity counts, Shelly sensor states and 129/121 device discrepancy could not be independently verified with the available read-only access. The status model was tested with isolated Registry/State fixtures.
- Changing a filter can add or remove HomeKit services. Only the tested isolated HAP identity path is evidenced. No Apple Home pairing guarantee is made.
- Reconcile is read-only; rollback requires explicit separate authorization and a fresh consistency check. See [upgrade and recovery](UPGRADE_0_10_0.md) and [write authorization](WRITE_AUTHORIZATION_0_10_0.md).

The GitHub release, installation in an existing Home Assistant instance and productive Writer activation are three separate steps. This release performs only the first.
