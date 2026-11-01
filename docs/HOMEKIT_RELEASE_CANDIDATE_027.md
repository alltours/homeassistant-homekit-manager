# HomeKit Manager 0.10.27 – Release Candidate

## Product boundary

This release candidate targets the unmodified official Home Assistant Core
2026.10.4. It provides HomeKit bridge inventory, diagnostics, planning,
preview, export and the narrowly scoped, administrator- and grant-gated
filter Apply path. Native UI↔YAML source migration, Config Entry source
changes, pairing changes and direct HAP persistence mutation remain disabled.

## Verified acceptance

- Full official-Core startup with two real loopback HAP bridges: **TEST VERIFIED**.
- Authenticated WebSocket plan/apply: **TEST VERIFIED**.
- Independent aiohomekit accessory verification: **TEST VERIFIED**.
- Pairing reconnect after a full Core restart: **TEST VERIFIED**.
- Multi-bridge isolation: **TEST VERIFIED**.
- Persistent package upgrade from 0.10.24 to 0.10.27: **TEST VERIFIED**.
- Stable local suite: **TEST VERIFIED**, 341 passed and 93 experimental tests
  deselected.
- Chromium and WebKit browser suites: **TEST VERIFIED**, 54 passed per engine.
- HACS and Hassfest: **CI VERIFIED** in the final branch workflow.

Final CI evidence:

- Stable CI run `41312372680`: <https://github.com/alltours/homeassistant-homekit-manager/actions/runs/41312372680>
- Quality: **CI VERIFIED**
- Browser: **CI VERIFIED**
- Official Core HAP acceptance: **CI VERIFIED**
- HAP evidence artifact `official-core-hap-acceptance-027`: **CI VERIFIED**
- HACS/Hassfest run `41312372606`: <https://github.com/alltours/homeassistant-homekit-manager/actions/runs/41312372606>
- HACS and Hassfest: **CI VERIFIED**

## Explicit limitation

An authenticated HACS UI installation and HACS UI upgrade were not executed in
the available environment. Package-level installation into a real isolated
official Core was verified, but it is not equivalent to HACS UI acceptance.
The release decision must therefore remain conditional until that external UI
gate is completed or the release claim is explicitly limited to the tested
package installation path.

## Reproduction

```text
python -m pytest -q tests -m 'not experimental_core'
npm run test:frontend
npx playwright test -c tests/frontend/playwright.config.mjs \
  tests/frontend/browser_regression.spec.mjs \
  tests/frontend/multi_bridge.spec.mjs \
  tests/frontend/screenshot_reference.spec.mjs \
  tests/frontend/ux_compact.spec.mjs --project=chromium --workers=1
npx playwright test -c tests/frontend/playwright.config.mjs \
  tests/frontend/browser_regression.spec.mjs \
  tests/frontend/multi_bridge.spec.mjs \
  tests/frontend/screenshot_reference.spec.mjs \
  tests/frontend/ux_compact.spec.mjs --project=webkit --workers=1
```

No official release or production installation is performed by this branch.
