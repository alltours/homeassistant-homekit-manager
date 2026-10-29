# HomeKit Manager 0.10.5 development checkpoint

## Starting point

- Base: released v0.10.4, commit `94d8e30` on `origin/main`.
- Branch: `feature/homekit-manager-0.10.5-production`.
- Productive Home Assistant, HomeKit configuration and pairing state were not modified.

## Completed, 2026-10-29

- Operation-bound filter writes and migration evidence were committed and pushed in `1c11bd1`.
- The backend resolves complete area, device and selection bulk scopes from its own current inventory. Hidden, disabled, diagnostic, configuration, missing-registry, missing-state, unsupported, conditional and unverified entities are excluded from automatic changes. Forged new includes are rejected by the server-side planner.
- The filter-reason wire field now matches the UI. A regression test covers the alias.
- Core 2026.11.0b0 compatibility classification is version-gated and includes the added ozone and sulphur-dioxide mappings; future Core versions remain unknown. Native filter-Apply beta validation and positive-list migration have separate capability gates.
- The devices view groups real areas and devices without synthetic cards for device-less entities, offers separate include/exclude actions and display options, shows scoped status/counts and keeps technical details collapsible.
- Full Core 2026.10.4 Python suite: 253 passed. Full Chromium/WebKit browser suite: 86 passed. The isolated full HA/HAP process restart and reconnect test passed in 104 seconds after raising the macOS subprocess timeout from 90 to 240 seconds. Frontend unit, JS syntax, Ruff, Bandit, pip check and npm audit passed. A second ZIP build matched byte-for-byte.

## Open release gates

1. Finish the currently running isolated Core 2026.11.0b0 pair/filter/reconnect probe and inspect its result.
2. Review the final CI runs, HACS/hassfest and dependency audit on the pushed release candidate. Address any findings without broadening the feature scope.
3. Review required PR approvals and branch protection before any merge or release; download and verify remote release assets only after a true GO.
4. Physical Apple Home validation and productive 0.10.5 installation are not authorized or claimed.

## Next concrete step

Poll the isolated Core beta probe, push the versioned release candidate and open a PR for the final CI and review gates. No release before every mandatory gate has evidence.
