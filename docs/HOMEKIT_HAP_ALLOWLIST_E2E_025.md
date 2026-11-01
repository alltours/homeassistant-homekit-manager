# HomeKit Manager 0.10.25 – HAP Allowlist E2E

## Stable boundary

The stable package never performs native UI↔YAML source migration, pairing
reset or direct HAP persistence mutation. Filter Apply is revision- and
authority-gated and must be verified against the actual HAP accessory list.

## Existing real HAP evidence

The isolated Core worker `_hap_full_bootstrap_worker.py` was executed twice:

- `HKM_FULL_BOOTSTRAP_PHASE=pair`: passed
- `HKM_FULL_BOOTSTRAP_PHASE=reconnect`: passed

The worker used Home Assistant Core 2026.10.4, a real HAP TCP bridge and an
`aiohomekit` controller. Pairing data was reused during reconnect; no second
pairing was created.

Status: **TEST VERIFIED** for isolated HAP bootstrap/reconnect.

The official-Core integration tests also passed the real HAP loopback checks:

- `tests/integration/test_hap_loopback_0100.py`: 2 passed
- `tests/integration/test_hap_yaml_loopback_0100.py`: 1 passed
- `tests/integration/test_write_grant_0100.py tests/integration/test_operation_service_0924.py`: 18 passed

These are isolated Core/test-authority checks. They do not constitute a fresh
25-plus-25 live Apply through an installed production HACS instance.

## 25-plus-25 acceptance

The repository contains prior synthetic 25-entity HAP and allowlist workers,
but a new 0.10.25 run through the regular stable UI/WebSocket Apply path was
not completed in the isolated official-Core instance.

Status: **NOT VERIFIED**.

Until completed, the stable product must not claim that an authorized Apply has
been independently verified by the live HAP accessory list.

