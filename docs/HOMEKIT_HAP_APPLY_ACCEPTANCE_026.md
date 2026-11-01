# HomeKit Manager 0.10.26 – HAP Apply Acceptance

## Test design

The acceptance worker uses two Home Assistant Core HomeKit Config Entries:

* Bridge A: `acceptance-bridge-a-026`, its own HAP port and include filter for
  25 `input_boolean.hkm_a_*` entities.
* Bridge B: `acceptance-bridge-b-026`, a separate HAP port and include filter for
  25 `input_boolean.hkm_b_*` entities.

Both bridges are paired independently with aiohomekit before any Apply.

The Apply is sent through the real authenticated Core WebSocket endpoint:

1. `homekit_manager/operation_plan`
2. `homekit_manager/operation_apply`
3. Core Config Entry options update and HomeKit reload
4. independent aiohomekit accessory reads
5. full Core restart and second independent reconnect

The worker creates an isolated, time-limited local test write grant. This is a
test-only authority in a temporary configuration; the product's native
UI↔YAML migration remains locked.

## Mutation and oracle

Bridge A removes `Hkm A 00` and includes `Hkm B 00`; the other A entities remain
unchanged. Bridge B is not targeted. Independent HAP evidence records:

* MAC and TCP port for both bridges,
* accessory names,
* accessory count,
* name→AID/IID signatures,
* same-pairing reconnect after Apply and after Core restart.

Retained Bridge A accessory signatures are compared by name. Bridge B's full
signature map is required to be byte-for-byte equivalent in the evidence JSON.
Exactly two HomeKit Config Entries must be present.

## Results

**TEST VERIFIED** – three fresh local WebSocket/HAP runs passed:

| Run | Pairing | WebSocket plan/apply | Bridge A | Bridge B | Restart reconnect |
|---|---|---|---|---|---|
| 1 | passed | `verified` / runtime `verified` | expected mutation, MAC/signatures retained for retained accessories | unchanged | passed |
| 2 | passed | `verified` / runtime `verified` | same | unchanged | passed |
| 3 | passed | `verified` / runtime `verified` | same | unchanged | passed |

Representative evidence directories were fresh `/tmp/hkm026-acceptance.*`
directories and were not added to the repository.

## Scope limitation

This acceptance covers the regular Stable filter Apply path for an existing
SOURCE_USER bridge. It does not activate or validate native UI↔YAML source
migration, YAML source mutation, or an Apple Home controller. Those remain
outside the Stable product scope.
