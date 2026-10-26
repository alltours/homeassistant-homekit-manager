# HomeKit Manager 0.9.17

Home Assistant custom integration for HomeKit Bridge inventory management, safe configuration planning and a version-bound controlled apply path.

## Features

- Entity, device, and area inventory from Home Assistant registries.
- Read-only discovery of existing HomeKit bridge config entries.
- HomeKit filter and compatibility status evaluation.
- Admin-protected WebSocket commands for inventory, validation, preview, drafts, and export.
- Native Home Assistant panel with search, filters, sorting, multi-selection, draft planning, preview, and export.
- Explicit multi-bridge context selection with bridge-scoped drafts and conflict protection.
- Persistent, secret-free draft history with restore-as-draft and read-only rule previews.
- Controlled application for existing `SOURCE_USER` HomeKit entries on Core 2026.10.4.

## Safety model

The integration does not manipulate pairings, accessory identifiers or `.storage` data. The apply path is restricted in the backend to an administrator, Core 2026.10.4, a uniquely selected `SOURCE_USER` HomeKit entry, a fresh validated diff and a successfully loaded entry after activation. YAML-imported entries, migrations and bridge creation/deletion remain blocked.

Version 0.9.17 is developed as a stabilization line; no GitHub release or productive installation is implied by this branch.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

## Installation

Install `custom_components/homekit_manager/` through HACS or copy it into the Home Assistant configuration directory after reviewing the release and backup plan. Create the integration through the Home Assistant UI. A Core restart is required after changing custom-component files.

## Development

The integration targets Home Assistant Core 2026.10.4 and Python 3.14+. The integration test dependencies are pinned in `tests/integration/requirements-ha-2026.10.4.txt`.

```bash
python -m pip install -r tests/integration/requirements-ha-2026.10.4.txt
pytest -c tests/integration/pytest.ini -q tests/integration tests/test_homekit_manager.py
node tests/frontend/test_panel.mjs
node --check custom_components/homekit_manager/www/homekit-manager.js
```

## Release process

Changes are developed on a branch, tested locally, committed, pushed to `main`, and verified by GitHub Actions. Starting with `0.9.2`, versioned GitHub Releases use the `0.9.x` series. Existing `1.0.x` releases remain historical. Versioned GitHub Releases are used for HACS installation.

See [the 0.9.2 implementation notes](docs/HOMEKIT_MANAGER_0_9_2.md).
See [the 0.9.3 implementation notes](docs/HOMEKIT_MANAGER_0_9_3.md).
See [the 0.9.4 implementation notes](docs/HOMEKIT_MANAGER_0_9_4.md).
See [the 0.9.5 implementation notes](docs/HOMEKIT_MANAGER_0_9_5.md).
See [the 0.9.6 implementation notes](docs/HOMEKIT_MANAGER_0_9_6.md).
See [the 0.9.7 implementation notes](docs/HOMEKIT_MANAGER_0_9_7.md).
See [the 0.9.8 implementation notes](docs/HOMEKIT_MANAGER_0_9_8.md).
See [the 0.9.9 implementation notes](docs/HOMEKIT_MANAGER_0_9_9.md).
See [the 0.9.11 stabilization notes](docs/HOMEKIT_MANAGER_0_9_11.md).
See [the 0.9.17 stabilization notes](docs/HOMEKIT_MANAGER_0_9_17.md).

## HACS status

The repository uses the supported single-integration layout, includes `hacs.json`, and is public for HACS discovery. See `docs/HACS_STATUS.md` and `docs/HOMEKIT_MANAGER_GITHUB_UPDATE.md` for the publication and update process.

## Known limitations

- No production Home Assistant installation is managed by this repository.
- YAML-imported HomeKit entries are intentionally not writable through the standard adapter.
- Migration between configuration methods is not automatic.
- The final release gate requires a real authenticated WebSocket E2E run against an isolated paired bridge.
- Browser regression coverage includes Chromium and WebKit viewport/theme tests; production browser acceptance remains separate.

