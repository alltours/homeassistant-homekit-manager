# HomeKit Manager 0.10.20 – CI Quality Gates

## Implemented gates

The regular CI quality job now runs:

```text
pytest -q tests -m "not experimental_core"
```

This prevents experimental Core migration tests from silently running against
the normal Home Assistant dependency. The `experimental_core` marker is
registered in `pytest.ini`.

The workflow continues to run JSON/integration structure validation, release
reproducibility, dependency consistency, Python compilation, Ruff, frontend
unit tests and the production-write-boundary checks. The browser job runs
Chromium and WebKit separately with one worker each.

## Experimental Core gate

The new `experimental-core-native` job is fail-closed and runs only when the
repository provides all three pinned variables:

- `HKM_EXPERIMENTAL_CORE_ARCHIVE_URL`
- `HKM_EXPERIMENTAL_CORE_ARCHIVE_SHA256`
- `HKM_EXPERIMENTAL_CORE_COMMIT`

It downloads and verifies the archive, requires the patched migration module,
and runs `scripts/run_experimental_core_tests.py`. Without a trusted archive
source in repository variables the job is skipped rather than falsely green;
the current repository therefore has no CI evidence for this job.

## Local evidence versus CI evidence

All results in this sprint were local executions. They are `TEST VERIFIED`,
not `CI VERIFIED`. No GitHub Actions run or PR status was available during the
sprint. HACS and Hassfest are defined in `.github/workflows/hacs.yml`, but no
local executables were installed and no remote Actions result was claimed:
`NOT VERIFIED`.

## Parallelization policy

Unit and browser tests are parallelizable when their fixture/server isolation
is respected. Full-Core workers use deterministic lock-backed HTTP/HAP ports
and fresh filesystems. The primary quality job remains serial at pytest level;
this is deliberate because it avoids external Core subprocess interference
while retaining independent port allocation for future parallel workers.
