# HomeKit Manager 0.10.5

Version 0.10.5 makes area and device bulk actions conservative and moves their
scope calculation to the server. Both actions preview the complete node,
show changed, unchanged and skipped counts, and save confirmed changes only
to the Manager draft. The devices view groups entities without a device
directly under their area and hides technical and disabled entries by default.
Publishing this version does not install it on Home Assistant.

Home Assistant custom integration for inspecting existing HomeKit Bridges and
planning changes in one four-tab panel: HomeKit, Devices, Changes and Settings.
The complete 0.10.0 reference remains Home Assistant Core **2026.10.4**. The
native Bridge filter writer is also isolated-tested on **2026.11.0b0**; YAML
writing is not extended to that beta. The beta compatibility projection is
version-gated; future Core versions remain unverified.
Native `SOURCE_USER` Bridges and
simple direct or directly included YAML `SOURCE_IMPORT` Bridges retain their
original source. Filter-list changes are the only supported write operation.
Complex or ambiguous YAML structures and accessory-mode entries remain
read-only. No YAML ↔ UI migration is performed.

Supported existing Bridge filter operations require an administrator, an exact
server-held operation ID, source, complete revision and concrete diff confirmation.
The legacy direct Apply route remains blocked. The one-hour Bridge-bound native
test mode and local grant remain available; neither is activated by an
installation or release. See
[test-mode authorization](docs/TEST_WRITE_MODE_0_10_1.md) and
[local authorization and recovery](docs/WRITE_AUTHORIZATION_0_10_0.md).
The release process does not activate a test mode or grant on any installation.

Core 2026.10.4 pins Pillow 12.3.0, for which upstream lists security
advisories fixed in 13.0.0. The [Python dependency decision](docs/SECURITY_PYTHON_DEPENDENCIES_0_10_0.md)
records the exact platform risk and the CI boundary: all advisories remain
visible, while new or manager-reachable findings block the release. Installing
HomeKit Manager does not change Core's Pillow dependency.

The inventory WebSocket API is paginated at 500 entities per response.
[Isolated performance measurements](docs/PERFORMANCE_0_10_0.md)
separate computation, authenticated transport and browser rendering.

See the [0.10.0 release notes](docs/RELEASE_0_10_0.md),
[upgrade and rollback guide](docs/UPGRADE_0_10_0.md), and
[development evidence](docs/DEVELOPMENT_0_10_0.md) before installation.

Existing bridges keep their original configuration source. YAML ↔ UI source
migration and Config Entry `source` changes are outside 0.10.0. Internal value translation is retained for reading, validation
and adapter-specific planning; it never changes an existing bridge's source.

Home Assistant custom integration for reading existing HomeKit Bridges, inspecting entities and safely planning configuration changes. Continues the 0.9.18 implementation; no new bridge or pairing is created.

## Features

- HomeKit, Devices, Changes and Settings views with theme-aware, responsive layouts.
- Entity/device/area inventory with six exclusive status classes and registry/device-ID reconciliation; search, filters and explicit bulk draft selection.
- Separate native configuration source and Manager administration metadata.
- Atomic draft files with optimistic conflict checks, per-bridge merging, export and bounded history.
- Durable activation evidence: interrupted operations recover as unknown; no automatic retry.
- Admin-protected WebSocket API, consistent snapshot responses and event-driven updates with event/recompute/CPU counters.
- Version-gated, side-effect-free compatibility projection for Home Assistant Core 2026.10.4 and 2026.11.0b0. Eligibility and filter inclusion do not prove Apple Home publication.

## Safety

**No installation, test-mode activation or filter Apply occurs during release.** Administrative ownership only stores Manager metadata. It does not migrate native HomeKit configuration or move pairing data. The confirmed operation path is restricted to an existing Bridge, current source and revision, filter-only diff and server-side authority checked again at mutation. The optional in-memory native test mode remains a separate Admin action with a one-hour expiry. Productive installation and the first Apply are separate decisions.

Drafts use `homekit_manager.yaml` and its backup; Manager metadata uses separate `homekit_manager.*` Home Assistant stores. Native HomeKit keys, pairings and identifiers are never read into these stores. The old `allow_production=True` shortcut is rejected. The operation path additionally requires an exact operation-ID confirmation; legacy direct Apply remains locked.

There is no retrospective proof for an older activation that was only kept in process memory. A loaded bridge is a current observation and does not resolve an unknown historical operation.

## Development and release

Use Python 3.14.2 or later. The verified local runtime was Python 3.14.9 with Home Assistant Core 2026.10.4 and an isolated native/HAP probe on 2026.11.0b0. Install `tests/integration/requirements-ha-2026.10.4.txt` for the full suite or `tests/integration/requirements-ha-2026.11.0b0.txt` for the beta native probe, then run `npm ci` and `npx playwright install chromium webkit`.

Run `pytest -q`, `npm run test:frontend` and `npm run test:browser`. The Python suite includes real authenticated Home Assistant WebSocket/browser tests when pinned browser dependencies are installed. Each integration test receives a separate temporary configuration directory. The five-minute browser observation is `npx playwright test -c tests/frontend/playwright.config.mjs tests/frontend/browser_stability.spec.mjs`.

Build with `python scripts/build_release.py --output .release`. After intentional source changes update the checked release file list with `--update-manifest`. The builder rejects unknown files and version/hash mismatches, uses fixed ZIP metadata and verifies every archived source byte. Repeat the build and compare the ZIP bytes. Before release, extract the ZIP into a temporary validation directory with the repository tests/tooling and run all checks there.

The authoritative product repository is `https://github.com/alltours/homeassistant-homekit-manager`. Older copied sources and historical reports describe historical releases only.

## Installation and limits

Review the [0.10.0 upgrade and rollback guide](docs/UPGRADE_0_10_0.md) before any installation decision. This repository does not prove the currently installed production version or Apple Home behavior. No production installation was performed during this work. Replacing custom-component files does not itself update a running Home Assistant process.

Accessory-mode instances are reported separately and cannot be selected as bridge targets. Cross-source migration and bridge creation/deletion stay blocked. Unverified future Core versions remain unknown and automatic bulk actions fail closed. Browser tests cover Chromium and WebKit; physical iPhone and VoiceOver acceptance remains separate. See the [0.10.5 release notes](docs/RELEASE_0_10_5.md), [UX target](docs/UX_BULK_ACTIONS_0_10_3.md) and [0.10.1 test-mode notes](docs/RELEASE_0_10_1.md) for the exact scope.

## License

MIT; see [LICENSE](LICENSE).
