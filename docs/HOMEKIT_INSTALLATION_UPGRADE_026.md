# HomeKit Manager 0.10.26 – Installation and Upgrade Acceptance

## Installation status

**BLOCKED** for the strict “HACS UI installation and authenticated onboarding”
gate. A browser-authenticated HACS UI session and GitHub token were not
available in the isolated environment. A copied HACS-compatible integration
payload was loaded by a real official Core process, but that is not equivalent
to a HACS UI installation and is not reported as one.

The real-Core worker did verify the package-level installation boundary:

* `custom_components/homekit_manager` was copied into the temporary HA config.
* Core loaded the integration and emitted the expected unverified-custom-
  integration warning.
* the manager Config Entry reached `loaded`.
* panel/WebSocket registration completed sufficiently for the authenticated
  WebSocket Apply test.
* no experimental Core patch was present.

Those points are **TEST VERIFIED**, but Gate B remains **NOT VERIFIED** because
the required HACS UI path was not executed.

## Persistent upgrade status

**TEST VERIFIED** for an isolated package upgrade, not for a HACS UI upgrade.

The 0.10.24 component was reconstructed from the repository commit
`b356f529140dd0dc862cf4a9299eefa983021901b` into a temporary source directory.
The baseline worker installed that component, started Core, created the two
bridges, paired both controllers, and persisted the manager/HomeKit state. The
same temporary configuration was then restarted after installing the current
0.10.26 component. Both pairings reconnected without repairing; MACs, ports,
accessory signatures and the two-bridge count were verified.

This proves persistence across the tested component replacement boundary. It
does not prove HACS UI upgrade mechanics.

## Reproduction

```sh
old_root=$(mktemp -d /tmp/hkm026-old.XXXXXX)
git archive b356f52 custom_components/homekit_manager | tar -x -C "$old_root"
old_component="$old_root/custom_components/homekit_manager"
run_dir=$(mktemp -d /tmp/hkm026-upgrade.XXXXXX)

HKM_ACCEPTANCE_DIR="$run_dir" HKM_ACCEPTANCE_PHASE=pair_apply \
HKM_ACCEPTANCE_SKIP_APPLY=1 \
HKM_ACCEPTANCE_COMPONENT_SOURCE="$old_component" \
PYTHONPATH=tests/integration:tests/acceptance \
<official-core-venv>/bin/python -u tests/acceptance/real_core_hap_apply_026.py

HKM_ACCEPTANCE_DIR="$run_dir" HKM_ACCEPTANCE_PHASE=reconnect \
PYTHONPATH=tests/integration:tests/acceptance \
<official-core-venv>/bin/python -u tests/acceptance/real_core_hap_apply_026.py
```

The baseline manifest reports `0.10.24`; the reconnect phase requires the
current manifest to report `0.10.26` and verifies the persistent HAP state.

## Remaining release gate

**BLOCKED** – perform the same upgrade through an authenticated HACS UI or an
equivalent HACS update transaction in a dedicated CI/browser environment, then
repeat the two-restart and pairing assertions.
