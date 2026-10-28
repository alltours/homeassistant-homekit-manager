# HomeKit Manager 0.10.0

Home Assistant custom integration for inspecting existing HomeKit Bridges and
planning changes in one four-tab panel: HomeKit, Devices, Changes and Settings.
It supports Home Assistant Core **2026.10.4**. Native `SOURCE_USER` Bridges and
simple direct or directly included YAML `SOURCE_IMPORT` Bridges retain their
original source. Filter-list changes are the only supported write operation.
Complex or ambiguous YAML structures and accessory-mode entries remain
read-only. No YAML ↔ UI migration is performed.

Production apply is disabled by default. A later, explicit, local, entry-bound
filter grant is required in addition to Home Assistant admin authorization and
operation confirmation; see [authorization and recovery](docs/WRITE_AUTHORIZATION_0_10_0.md).
No grant was placed on the existing production installation. Publishing this
version does not install it or authorize a productive apply.

Core 2026.10.4 pins Pillow 12.3.0, for which upstream lists security
advisories fixed in 13.0.0. The [Python dependency decision](docs/SECURITY_PYTHON_DEPENDENCIES_0_10_0.md)
records the exact platform risk and the CI boundary: all advisories remain
visible, while new or manager-reachable findings block the release. Installing
HomeKit Manager does not change Core's Pillow dependency.

The inventory WebSocket API is paginated at 500 entities per response in this
branch. [Isolated performance measurements](docs/PERFORMANCE_0_10_0.md)
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
- Side-effect-free compatibility projection for Home Assistant Core 2026.10.4. Eligibility and filter inclusion do not prove Apple Home publication.

## Safety in 0.10.0

**Applying HomeKit changes is disabled by default in the backend and visibly disabled in the panel.** Administrative ownership only stores Manager metadata. It does not enable the writer, migrate native HomeKit configuration, reload a bridge or move pairing data. A separately created, time-limited local grant can enable one bridge's filter writer; it was tested only in isolated Core instances. Productive installation and writer activation are separate decisions.

Drafts use `homekit_manager.yaml` and its backup; Manager metadata uses separate `homekit_manager.*` Home Assistant stores. Native HomeKit keys, pairings and identifiers are never read into these stores. The old `allow_production=True` shortcut is rejected. The only productive filter path requires the separately verified local grant described above.

There is no retrospective proof for an older activation that was only kept in process memory. A loaded bridge is a current observation and does not resolve an unknown historical operation.

## Development and release

Use Python 3.14.2 or later. The verified local runtime was Python 3.14.9 and Home Assistant Core 2026.10.4. Install `tests/integration/requirements-ha-2026.10.4.txt`, then run `npm ci` and `npx playwright install chromium webkit`.

Run `pytest -q`, `npm run test:frontend` and `npm run test:browser`. The Python suite includes real authenticated Home Assistant WebSocket/browser tests when pinned browser dependencies are installed. Each integration test receives a separate temporary configuration directory. The five-minute browser observation is `npx playwright test -c tests/frontend/playwright.config.mjs tests/frontend/browser_stability.spec.mjs`.

Build with `python scripts/build_release.py --output .release`. After intentional source changes update the checked release file list with `--update-manifest`. The builder rejects unknown files and version/hash mismatches, uses fixed ZIP metadata and verifies every archived source byte. Repeat the build and compare the ZIP bytes. Before release, extract the ZIP into a temporary validation directory with the repository tests/tooling and run all checks there.

The authoritative product repository is `https://github.com/alltours/homeassistant-homekit-manager`. Older copied sources and historical reports describe historical releases only.

## Installation and limits

Review the [0.10.0 upgrade and rollback guide](docs/UPGRADE_0_10_0.md) before any installation decision. This repository does not prove the currently installed production version or Apple Home behavior. No production installation was performed during this work. Replacing custom-component files does not itself update a running Home Assistant process.

Accessory-mode instances are reported separately and cannot be selected as bridge targets. Cross-source migration and bridge creation/deletion stay blocked. Versions other than Core 2026.10.4 receive unknown compatibility rather than a positive claim. Browser tests cover Chromium and WebKit; physical iPhone and VoiceOver acceptance remains separate.

## License

MIT; see [LICENSE](LICENSE).
