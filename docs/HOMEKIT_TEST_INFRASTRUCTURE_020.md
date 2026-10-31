# HomeKit Manager 0.10.20 – Test Infrastructure

## Scope

This document records the test-infrastructure changes on
`feature/homekit-manager-0.10.20-test-infrastructure`. Productive Home
Assistant files, bridges, pairings and HAP persistence were not accessed.

## Repository pins

| Component | Branch | Commit | Status |
|---|---|---|---|
| Manager | `feature/homekit-manager-0.10.20-test-infrastructure` | based on `b609258ddd472c7f8fcd97f8571ed894d20c94fc` | CODE VERIFIED |
| Core prototype | `hkm-native-migration-poc-2026.10.4-0.10.20-test-infrastructure` | `c04fa739c790169977447b0373e5c26e7e334021` | CODE VERIFIED |

The Core checkout is an isolated local prototype. It was not pushed to the
official Home Assistant Core remote.

## Test layers

| Layer | Main entry point | Core requirement | Isolation |
|---|---|---|---|
| Manager unit/integration | `pytest -q tests -m "not experimental_core"` | installed official Core | pytest temp dirs and fixture port allocation |
| Experimental Core | `scripts/run_experimental_core_tests.py` | exact pinned prototype | exact Git commit, module-path probe, temp Core dirs |
| Full-Core HAP | `tests/integration/test_core_*.py` | experimental Core | subprocess worker, temp config, real aiohomekit |
| Browser backend | `tests/integration/test_browser_backend.py` | installed official Core | fixture HA instance and unique HTTP port |
| Frontend browser | `npm run test:browser` | Node/Playwright | Playwright browser contexts and local fixture server |
| Frontend unit | `npm run test:frontend` | Node | no HA or production state |

## Port isolation

`tests/integration/port_allocator.py` allocates deterministic ports from two
disjoint ranges:

- HTTP: `18000–27999`
- HAP: `28000–37999`

Allocation is based on SHA-256 of the test identity and protected by a
process-held `fcntl.flock()` lock file in `/tmp` (override with
`HKM_TEST_PORT_LOCK_DIR`). The same identity is stable within a worker
process. A lock prevents cooperating workers from selecting the same port;
the Home Assistant/HAP bind remains the final operating-system authority.
This is stronger than free-port-then-close, but it cannot reserve ports
against unrelated non-cooperating applications.

Full-Core workers write their HTTP port into their own
`configuration.yaml`. HAP ports are persisted in each worker's temporary
state and remain stable across crash/restart phases.

## Filesystem isolation

Every Full-Core scenario uses a fresh `TemporaryDirectory`. Its configuration,
`.storage`, YAML includes, migration journal, snapshots, locks, HAP persistence,
pairing material and logs are below that directory. Pairing material is chmod
`0600` where the worker persists it and is never printed in test output.

## HAP bootstrap

Workers now distinguish ConfigEntry loaded from HAP listener readiness. Before
pairing they perform a bounded TCP readiness check against the expected loopback
HAP port. The multibridge and native-source workers permit one retry only for
`aiohomekit.AuthenticationError` during the initial bootstrap/reconnect phase;
the retry is logged, requires the bridge to remain unpaired, and the original
error is raised unchanged if the second attempt fails. This is not a general
assertion retry.

## Core checkout guard

`scripts/run_experimental_core_tests.py` requires an explicit checkout and can
require an exact commit and version. Before pytest starts it verifies:

1. the checkout is a Git repository;
2. `HEAD` matches the requested commit;
3. `homeassistant/components/homekit/migration.py` exists;
4. imported `homeassistant` and the migration module resolve inside that checkout;
5. all expected Core migration callables exist.

The wrong-commit negative control exited with code `1` before pytest started:
`expected 000...000, loaded c04fa739...`. This is TEST VERIFIED.

## Browser E2E correction

The backend Node test asserted the historical Manager version `0.10.14` while
the manifest is `0.10.18`. The Python test now reads the manifest version and
passes it to `backend_e2e.mjs`; the Node test asserts the supplied version.
Chromium and WebKit now execute the same real backend assertions successfully.

## Production boundary

No production migration endpoint was enabled. The changes are confined to
test workers, test fixtures, test selection, browser test plumbing, CI
selection and the fail-closed experimental Core runner.
