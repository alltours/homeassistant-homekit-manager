# HomeKit Manager 0.9.24

> Version 0.10.0 is in development on `feature/homekit-manager-0.10.0`.
> The [0.10.0 development checkpoint](docs/DEVELOPMENT_0_10_0.md) records
> verified changes and unresolved release gates. It is not an installable
> 0.10.0 release.

The development branch contains a narrowly scoped local filter write grant;
see [authorization and recovery](docs/WRITE_AUTHORIZATION_0_10_0.md). It has
only been exercised against isolated Home Assistant Core instances. No grant
was placed on the existing production installation, and this branch is not
approved for installation.

The inventory WebSocket API is paginated at 500 entities per response in this
branch. [Isolated performance measurements](docs/PERFORMANCE_0_10_0.md)
separate computation, authenticated transport and browser rendering.

> Release source for HomeKit Manager 0.9.24. This work did not install the
> integration in the production Home Assistant environment. See
> [development status](docs/DEVELOPMENT_0_9_24.md) for tested paths and release
> gates. Production HomeKit application remains server-side disabled.

Existing bridges keep their original configuration source. YAML ↔ UI source
migration and Config Entry `source` changes are outside both 0.9.24 and the
planned 0.10.0. Internal value translation is retained for reading, validation
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

## Safety in 0.9.24

**Applying HomeKit changes is disabled in the backend and visibly disabled in the panel.** Administrative ownership only stores Manager metadata. It does not enable the writer, migrate native HomeKit configuration, reload a bridge or move pairing data. No production deployment is part of this remediation.

Drafts use `homekit_manager.yaml` and its backup; Manager metadata uses separate `homekit_manager.*` Home Assistant stores. Native HomeKit keys, pairings and identifiers are never read into these stores. The legacy writer is retained only behind an explicit isolated-test gate; `allow_production=True` is rejected.

There is no retrospective proof for an older activation that was only kept in process memory. A loaded bridge is a current observation and does not resolve an unknown historical operation.

## Development and release

Use Python 3.14.2 or later. The verified local runtime was Python 3.14.9 and Home Assistant Core 2026.10.4. Install `tests/integration/requirements-ha-2026.10.4.txt`, then run `npm ci` and `npx playwright install chromium webkit`.

Run `pytest -q`, `npm run test:frontend` and `npm run test:browser`. The Python suite includes real authenticated Home Assistant WebSocket/browser tests when pinned browser dependencies are installed. Each integration test receives a separate temporary configuration directory. The five-minute browser observation is `npx playwright test -c tests/frontend/playwright.config.mjs tests/frontend/browser_stability.spec.mjs`.

Build with `python scripts/build_release.py --output .release`. After intentional source changes update the checked release file list with `--update-manifest`. The builder rejects unknown files and version/hash mismatches, uses fixed ZIP metadata and verifies every archived source byte. Repeat the build and compare the ZIP bytes. Before release, extract the ZIP into a temporary validation directory with the repository tests/tooling and run all checks there.

The authoritative product repository is `https://github.com/alltours/homeassistant-homekit-manager`; local canonical location: `/Users/felixalshut/Documents/ChatGPT/homeassistant-homekit-manager`. Older copied sources and historical reports describe historical releases only. Current 0.10.0 development is on branch `feature/homekit-manager-0.10.0`.

## Installation and limits

Review the [0.9.24 scope and upgrade notes](docs/HOMEKIT_MANAGER_0_9_24.md) before any installation decision. This repository does not prove the currently installed production version or Apple Home behavior. No production installation was performed during this work. Replacing custom-component files does not itself update a running Home Assistant process.

Accessory-mode instances are reported separately and cannot be selected as bridge targets. Cross-source migration and bridge creation/deletion stay blocked. Versions other than Core 2026.10.4 receive unknown compatibility rather than a positive claim. Browser tests cover Chromium and WebKit; physical iPhone and VoiceOver acceptance remains separate.

## License

MIT; see [LICENSE](LICENSE).
