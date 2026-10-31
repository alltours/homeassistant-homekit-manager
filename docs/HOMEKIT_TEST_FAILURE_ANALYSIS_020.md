# HomeKit Manager 0.10.20 – Test Failure Analysis

## Evidence boundary

The independent 0.10.19 report supplied the aggregate historical figure of 57
failures. The raw pre-0.10.20 pytest output was not present in the repository,
so a complete one-to-one reconstruction of all 57 original test names is
`NOT VERIFIED`. The controlled reproduction below is the authoritative
0.10.20 evidence.

## Controlled failure sequence

### Browser backend failures

The known Chromium/WebKit backend failures were reproduced at the Node
assertion in `tests/frontend/backend_e2e.mjs`: the test expected `0.10.14`,
while `manifest.json` contained `0.10.18`. Root cause: stale test fixture
assumption, category `TEST_HARNESS_DEFECT`. The manifest-driven assertion was
implemented and both engines passed.

### First controlled full-suite residuals

Command:

```text
PYTHONPATH=<core>:/Users/felixalshut/Documents/ChatGPT/homeassistant-homekit-manager <venv>/bin/python -m pytest -q tests
```

Result before the residual fixes: `377 passed, 16 failed in 242.76s`.

| Count | Category | Root cause | Correction |
|---:|---|---|---|
| 15 | TEST_HARNESS_DEFECT | `_native_source_migration_worker_012.py` wrote uppercase `ROLLBACK_REQUIRED`, but strict journal validation accepts the persisted status `rollback_required` | corrected worker fixture status and retained strict loader |
| 1 | INVALID_TEST_ASSUMPTION | `test_missing_core_boundary_fails_closed` assumed an unpatched Core while the suite intentionally imported the patched Core | test now monkeypatches the adapter boundary to represent an absent capability |
| 1 subsequent isolated bootstrap failure | TIMING_OR_RACE | aiohomekit pair setup could begin after ConfigEntry load but before a stable HAP listener/bootstrap state | bounded listener readiness and one explicit AuthenticationError bootstrap retry |

The count in the first row includes repeated parameterized Full-Core cases with
the same proven invalid-status cause; it is not collapsed into a false
"flaky" label.

## Final controlled result

After the corrections:

- experimental full Manager suite: `393 passed, 0 failed, 0 skipped in 241.95s`
  — TEST VERIFIED;
- official-Core-compatible suite: `325 passed, 68 deselected in 20.15s` —
  TEST VERIFIED;
- browser backend: `2 passed in 1.92s` — TEST VERIFIED;
- Playwright Chromium/WebKit: `108 passed in 20.1s` — TEST VERIFIED.

The first CI run additionally exposed a runner-specific permissions issue in
write-grant tests. The test fixture now explicitly sets every pytest temporary
configuration directory to mode `0700`, preserving the production fail-closed
check while removing dependence on the runner umask. The beta runner was also
corrected to exclude tests marked `experimental_core`; those tests must run only
against the pinned experimental Core. A fresh beta environment then produced
`117 passed, 68 deselected` and the beta HAP filter/reconnect sequence passed.

The historical aggregate of 57 is therefore not claimed as fully reassembled
from raw evidence. The currently reproducible failures were all classified and
resolved or explicitly separated by a deterministic test gate.

## Non-product defects observed in logs

The isolated Core emits optional-environment warnings for missing turbojpeg
and ffmpeg. They do not affect the HomeKit scenarios and were not converted
into green assertions. They remain environment noise and should be installed
only if a future test actually exercises camera or ffmpeg behavior.
