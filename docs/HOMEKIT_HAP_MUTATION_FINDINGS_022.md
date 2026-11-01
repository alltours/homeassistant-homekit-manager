# 0.10.22 Security Findings

## HAP-022-01 – Identity was verified after HAP publication

- Severity: HIGH
- Status: FIXED in the local experimental Core patch
- Reproduction: mutate Bridge A's persisted MAC after a real Core SIGKILL, then
  restart Core while a migration is in `SOURCE_SWITCHED`/recovery.
- Previous behavior: the existing finalizer checked the MAC after
  `homekit.async_start()`, which was after bridge registration and HAP driver
  startup.
- Impact: a damaged identity could be briefly published before the mismatch was
  recorded.
- Correction: validate source/configuration, MAC, pairing fingerprint,
  accessory hash, and duplicate identity before `_async_register_bridge()` and
  `driver.async_start()`.
- Regression: real MAC mutation test passes in both migration directions.

## HAP-022-02 – Identified manual recovery blocked unrelated bridges

- Severity: HIGH
- Status: FIXED in the local experimental Core patch
- Reproduction: mutate Bridge A's allowlist or HAP state while Bridge B is
  independently paired and active.
- Previous behavior: `MANUAL_RECOVERY_REQUIRED` returned `False` for every
  HomeKit Entry, so Bridge B was also left stopped.
- Impact: local safety failure was broader than necessary and reduced
  availability of an unrelated bridge.
- Correction: an identified manual-recovery journal is scoped to its matching
  Entry identity; unrelated Entries continue. Journal corruption without a
  trusted identity remains conservative at the earlier reconciliation gate.
- Regression: all 11 mutation cases keep Bridge B reconnectable.

## HAP-022-03 – Pairing and accessory identity were not part of the durable
prepare contract

- Severity: HIGH
- Status: FIXED in the local experimental Core patch
- Correction: durable prepare stores hashes of pairing membership/public
  controller material and the baseline HAP accessory hash. The values exclude
  private bridge keys and are checked before publish and before final commit.
- Regression: pairing-loss and AID/IID mutation cases are detected without
  re-pairing.

## Residual limitations

- `TEST VERIFIED`: the mutations listed in the 0.10.22 campaign are detected in
  isolated macOS Full-Core processes.
- `NOT VERIFIED`: physical power-loss durability and filesystem-specific
  guarantees beyond the tested platform.
- `NOT VERIFIED`: Apple Home controller behavior; aiohomekit is the test
  controller.
- `NOT VERIFIED`: Core Beta compatibility for this new patch.
- `NO-GO`: production native migration remains disabled pending independent
  review and CI evidence for the new patch.
