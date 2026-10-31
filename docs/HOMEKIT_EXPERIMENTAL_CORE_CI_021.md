# HomeKit Manager 0.10.21 — Experimental Core CI

Status: development branch only. Native production migration remains disabled.

The integration manifest remains at `0.10.18`; `0.10.21` is the engineering
sprint/branch identifier and this change is not an official release.

## Purpose

This document defines the fail-closed CI gate for the experimental Home
Assistant Core migration prototype. The gate does not download a moving Core
archive. It checks out the official Core repository at an exact commit, applies
the reviewed patch stored in this repository, verifies the resulting Git tree,
checks the import path and capabilities, and only then starts pytest.

## Provenance

| Item | Value | Status |
|---|---|---|
| Manager base | `aa02e8f73227656b1137e14333c35aa7dd2deb7c` | CODE VERIFIED |
| Official Core tag | `2026.10.4` | CODE VERIFIED |
| Official Core base | `357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b` | CODE VERIFIED |
| Experimental Core target | `c04fa739c790169977447b0373e5c26e7e334021` | CODE VERIFIED |
| Target Git tree | `8419f460ab542256cbee6f8031a874e6f43608a4` | CODE VERIFIED |
| Patch SHA-256 | `ad8a0a1166d634c829978fb35be35b7894b9ea136011023e76e1fbb29dd23537` | CODE VERIFIED |
| Changed Core files | 4 | CODE VERIFIED |

## Gate sequence

The `experimental-core-native` job in `.github/workflows/ci.yml` is no longer
conditional on repository variables. It always performs these checks:

1. Verify that the checked-out Manager commit equals `GITHUB_SHA`.
2. Read the pinned Core base, target tree, file list, and patch digest from the
   reviewed manifest.
3. Clone `https://github.com/home-assistant/core.git` without checking out a
   moving branch.
4. Fetch and detach at the exact base commit.
5. Run `git apply --check` and apply the patch.
6. Verify the changed-file set and exact target tree hash.
7. Probe Core version, imported module paths, and required migration
   capabilities.
8. Collect the experimental marker and refuse an empty collection.
9. Run the selected tests and require non-empty JUnit evidence with zero
   skipped, failed, or errored tests.
10. Run the security negative controls and upload redacted evidence.

The workflow uploads JUnit XML, JSON summaries, the manifest, patch
verification output, Python/runtime information, and test commands. Pairing
secrets are not written to the artifacts.

## Local evidence

Command:

```text
python scripts/run_experimental_core_tests.py \
  --core-root /private/tmp/hkm-021-worktree-pvMqVC/core \
  --core-commit 357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b \
  --core-version 2026.10.4 \
  --expected-tree 8419f460ab542256cbee6f8031a874e6f43608a4 \
  --artifacts-dir /tmp/hkm-021-evidence-nAUmua \
  tests -m experimental_core
```

Result: `68 passed, 335 deselected, 0 skipped` in `218.11s`; JUnit reported
`tests=68`, `failures=0`, `errors=0`, `skipped=0`. The imported migration
module was inside the patched Core checkout. This is TEST VERIFIED.

The regular Manager suite was run separately with:

```text
python -m pytest -q tests -m 'not experimental_core'
```

Result: `335 passed, 68 deselected` in `20.49s`. This is TEST VERIFIED.

The new negative-control module reports `10 passed` in `0.19s`. Ruff,
`compileall`, `git diff --check`, patch application, changed-file verification,
and target-tree verification also passed locally. These are TEST VERIFIED.

## CI status

The final workflow run for Manager commit `83a296ceaada58bc3f8553fc0b5c9dad47f9b358`
completed successfully:

* Run ID: `41253834835`
* URL: <https://github.com/alltours/homeassistant-homekit-manager/actions/runs/41253834835>
* `quality`: success
* `browser`: success
* `core-beta-native`: success
* `experimental-core-native`: success
* Artifact: `experimental-core-ci-evidence` (uploaded, 3,963 bytes)

This is CI VERIFIED. The first run (`41252932837`) failed before any job because
`runner.temp` was used in a job-level environment context; `actionlint` caught
the defect, the paths were moved into a shell step, and the subsequent run
passed. The same first run also exposed a real HAP bootstrap race in the
regular suite; that was fixed before the final run.

## Security boundary

The patch is test infrastructure and experimental Core provenance only. It does
not enable the Manager's production write path, does not alter production
configuration, and does not change an official Home Assistant Core checkout.
