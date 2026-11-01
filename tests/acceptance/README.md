# HomeKit Manager 0.10.26 real-world acceptance

This directory contains the isolated official-Core acceptance worker. It never
uses the production configuration directory and does not install the
experimental Core patch.

## Reproduction

```text
mkdir -p /tmp/hkm026-acceptance
HKM_ACCEPTANCE_DIR=/tmp/hkm026-acceptance \
HKM_ACCEPTANCE_PHASE=pair_apply \
PYTHONPATH=tests/integration:tests/acceptance \
<official-core-venv>/bin/python tests/acceptance/real_core_hap_apply_026.py

HKM_ACCEPTANCE_DIR=/tmp/hkm026-acceptance \
HKM_ACCEPTANCE_PHASE=reconnect \
PYTHONPATH=tests/integration:tests/acceptance \
<official-core-venv>/bin/python tests/acceptance/real_core_hap_apply_026.py
```

The worker uses Home Assistant Core 2026.10.4, loopback HTTP/HAP ports,
synthetic `input_boolean` entities, two real HomeKit bridges, two independent
`aiohomekit` pairings, an authenticated Home Assistant WebSocket operation
plan/apply, and a temporary local write grant. Pairing secrets stay in the
temporary directory and are not part of repository artifacts.

For the persistent upgrade check, stage the 0.10.24 component from the
verified Git commit into a temporary directory, run the baseline with
`HKM_ACCEPTANCE_SKIP_APPLY=1` and `HKM_ACCEPTANCE_COMPONENT_SOURCE=...`, then
run the `reconnect` phase without that override. The reconnect phase installs
the current 0.10.26 component into the same config directory and verifies the
original HAP pairings after a full Core restart.
