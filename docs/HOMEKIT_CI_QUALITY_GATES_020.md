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

The first push of commit `7759582` exposed two CI-only issues. The quality job
failed because runner-created temporary directories did not always satisfy the
write-grant security precondition; the beta job incorrectly included
`experimental_core` tests against the unpatched official beta Core. Both causes
were corrected in the follow-up commit documented below.

The first HACS workflow run `41247564145` completed successfully: both HACS and
Hassfest are `CI VERIFIED`. The first general CI run `41247564342` was
`FAILED` before the follow-up correction; its experimental Core job was
skipped, as expected, because no trusted archive variables are configured.

The corrected commit requires a new GitHub Actions run before the final CI
state can be called `CI VERIFIED`. Local evidence remains `TEST VERIFIED`.

## Parallelization policy

Unit and browser tests are parallelizable when their fixture/server isolation
is respected. Full-Core workers use deterministic lock-backed HTTP/HAP ports
and fresh filesystems. The primary quality job remains serial at pytest level;
this is deliberate because it avoids external Core subprocess interference
while retaining independent port allocation for future parallel workers.
