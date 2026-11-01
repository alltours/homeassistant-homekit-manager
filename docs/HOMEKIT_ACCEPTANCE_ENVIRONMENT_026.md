# HomeKit Manager 0.10.26 – Acceptance Environment

## Scope

This document records the isolated real-Core acceptance environment. Native
UI↔YAML source migration remains disabled. No production configuration,
pairing, bridge, or HAP persistence is used.

## Environment

| Item | Value |
|---|---|
| Home Assistant Core | 2026.10.4, official Python distribution used by `.hkm-core-314` |
| Python | 3.14.9 on macOS arm64 for local runs |
| Network | loopback only; dynamically reserved HTTP and HAP TCP ports |
| Persistence | fresh `mktemp` directory per run |
| Bridges | two real Core HomeKit bridge Config Entries |
| Controllers | two independent `aiohomekit` controllers and pairings |
| Manager install | copied into temporary `config/custom_components/homekit_manager`, equivalent to a HACS package payload; HACS UI itself was not automated |

## Reproduction

```sh
run_dir=$(mktemp -d /tmp/hkm026-acceptance.XXXXXX)
HKM_ACCEPTANCE_DIR="$run_dir" HKM_ACCEPTANCE_PHASE=pair_apply \
  PYTHONPATH=tests/integration:tests/acceptance \
  /Users/felixalshut/Documents/ChatGPT/.hkm-core-314/bin/python \
  -u tests/acceptance/real_core_hap_apply_026.py

HKM_ACCEPTANCE_DIR="$run_dir" HKM_ACCEPTANCE_PHASE=reconnect \
  PYTHONPATH=tests/integration:tests/acceptance \
  /Users/felixalshut/Documents/ChatGPT/.hkm-core-314/bin/python \
  -u tests/acceptance/real_core_hap_apply_026.py
```

The worker creates 50 real `input_boolean` entities in the isolated Core
configuration, installs two HomeKit bridges with separate ports and filters,
starts the full Core lifecycle, and persists the resulting HAP state.

## Gate A

**TEST VERIFIED** – three fresh runs completed the full official-Core start,
HTTP/WebSocket setup, manager Config Entry setup, two HAP bridge startups,
pairing, and a later full Core restart/reconnect. The local environment emits
an optional `libturbojpeg` warning during Core discovery; it did not affect the
HomeKit or manager assertions.

The same worker is wired into the `acceptance` GitHub Actions job in
`.github/workflows/ci.yml`. Its CI status is only **CI VERIFIED** after the
post-push job has actually run and its evidence artifact has been inspected.

## Isolation properties

Each run owns its configuration directory, `.storage` files, YAML, HAP state,
pairings, HTTP port, HAP ports, operation records, and write grant. Pairing
JSON files are mode `0600` and remain in `/tmp` only.
