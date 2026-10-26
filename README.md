# HomeKit Manager

Home Assistant custom integration for read-only HomeKit Bridge inventory management and configuration planning.

## Features

- Entity, device, and area inventory from Home Assistant registries.
- Read-only discovery of existing HomeKit bridge config entries.
- HomeKit filter and compatibility status evaluation.
- Admin-protected WebSocket commands for inventory, validation, preview, drafts, and export.
- Native Home Assistant panel with search, filters, sorting, multi-selection, draft planning, preview, and export.

## Safety model

The integration is deliberately read-only with respect to HomeKit. `apply_enabled = False` is enforced and `HomeKitWriter.async_apply()` rejects every application attempt. The integration does not update HomeKit config entries, reload HomeKit, manipulate pairings, modify accessory identifiers, or write `.storage` data.

This project is still under development. A working local test suite does not constitute a production Home Assistant acceptance.

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

## HACS status

The repository uses the supported single-integration layout, includes `hacs.json`, and is public for HACS discovery. See `docs/HACS_STATUS.md` and `docs/HOMEKIT_MANAGER_GITHUB_UPDATE.md` for the publication and update process.

## Known limitations

- No production Home Assistant installation is managed by this repository.
- No supported API currently enables a safe direct update of an existing HomeKit config entry from this integration.
- Browser regression coverage is provided as a local fixture; CI runs the deterministic frontend behavior test and JavaScript syntax checks.

