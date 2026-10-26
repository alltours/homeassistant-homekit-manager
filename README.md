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

Copy `custom_components/homekit_manager/` into the Home Assistant configuration directory and restart Home Assistant only after reviewing the release and backup plan. Create the integration through the Home Assistant UI. Do not add this repository to a production HACS installation yet.

## Development

The integration targets Home Assistant Core 2026.10.4 and Python 3.14+. The integration test dependencies are pinned in `tests/integration/requirements-ha-2026.10.4.txt`.

```bash
python -m pip install -r tests/integration/requirements-ha-2026.10.4.txt
pytest -c tests/integration/pytest.ini -q tests/integration tests/test_homekit_manager.py
node tests/frontend/test_panel.mjs
node --check custom_components/homekit_manager/www/homekit-manager.js
```

## Release process

Changes are developed on a branch, tested locally, committed, pushed to `main`, and verified by GitHub Actions. GitHub Releases and HACS publication are intentionally not enabled by this repository snapshot.

## HACS status

The repository uses the supported single-integration layout and includes `hacs.json`. HACS cannot use this repository because it is private; HACS documents that private GitHub repositories are not supported. See `docs/HACS_STATUS.md` and `docs/HOMEKIT_MANAGER_GITHUB_UPDATE.md` for the cause and the supported authenticated GitHub update process.

## Known limitations

- No production Home Assistant installation is managed by this repository.
- No supported API currently enables a safe direct update of an existing HomeKit config entry from this integration.
- Browser regression coverage is provided as a local fixture; CI runs the deterministic frontend behavior test and JavaScript syntax checks.

