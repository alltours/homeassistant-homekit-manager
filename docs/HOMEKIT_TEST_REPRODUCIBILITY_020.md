# HomeKit Manager 0.10.20 – Reproducibility

## Environment

| Tool | Observed value |
|---|---|
| OS | macOS arm64 |
| Python | 3.14.9 |
| pytest | 9.0.3 |
| Node.js | v24.13.0 |
| npm | 11.6.2 |
| Core | 2026.10.4, commit `c04fa739c790169977447b0373e5c26e7e334021` |
| Playwright browser suite | Chromium and WebKit, 108 tests |

The Manager version in the manifest is `0.10.18`; the requested sprint is test
infrastructure work and does not change the product version.

## Commands and evidence

### Regular Manager gate

```text
/Users/felixalshut/Documents/ChatGPT/.hkm-core-314/bin/python -m pytest -q tests -m "not experimental_core"
```

Result: `325 passed, 68 deselected, 20.15s` — TEST VERIFIED. The run used the
installed official Core package; no `PYTHONPATH` override was used.

### Experimental full suite

```text
PYTHONPATH=/Users/felixalshut/Documents/ChatGPT/homeassistant-core-0.10.14-poc:/Users/felixalshut/Documents/ChatGPT/homeassistant-homekit-manager /Users/felixalshut/Documents/ChatGPT/.hkm-core-314/bin/python -m pytest -q tests
```

Result: `393 passed, 0 failed, 0 skipped, 241.95s` — TEST VERIFIED. The
checkout and import path were also validated through
`scripts/run_experimental_core_tests.py`.

### Experimental Core guard

```text
/Users/felixalshut/Documents/ChatGPT/.hkm-core-314/bin/python scripts/run_experimental_core_tests.py \
  --core-root /Users/felixalshut/Documents/ChatGPT/homeassistant-core-0.10.14-poc \
  --core-commit c04fa739c790169977447b0373e5c26e7e334021 \
  --core-version 2026.10.4 tests/test_core_migration.py
```

Result: `4 passed in 0.08s`, with exact commit, version, module path and
capability checks — TEST VERIFIED.

Wrong-commit control exited `1` before pytest — TEST VERIFIED.

### Full-Core regression groups

```text
pytest -q tests/integration/test_native_source_migration_012.py tests/integration/test_native_source_crash_recovery_013.py tests/integration/test_startup_recovery_lifecycle_013.py tests/integration/test_yaml_import_bootstrap_013.py
```

Result: `22 passed in 65.55s` — TEST VERIFIED.

```text
pytest -q tests/integration/test_core_persistence_faults_016.py tests/integration/test_core_transaction_protocol_017.py tests/integration/test_core_rollback_018.py
```

Result: `39 passed in 130.44s` — TEST VERIFIED.

The multi-bridge suite was independently repeated three times with fresh
temporary directories:

| Run | Result | Duration |
|---:|---|---:|
| 1 | `7 passed` | 22.97s |
| 2 | `7 passed` | 22.94s |
| 3 | `7 passed` | 23.11s |

All are TEST VERIFIED. No pairing was reused between runs.

### Browser gates

```text
npm run test:frontend
```

Result: `frontend panel behavior: ok` — TEST VERIFIED.

```text
pytest -q tests/integration/test_browser_backend.py
```

Result: `2 passed in 1.92s` (Chromium/WebKit) — TEST VERIFIED.

```text
npm run test:browser
```

Result: `108 passed in 20.1s` — TEST VERIFIED.

### Static checks

Ruff on all changed Python files, `python -m compileall -q tests/integration
scripts/run_experimental_core_tests.py`, workflow YAML parsing and
`git diff --check` all passed — TEST VERIFIED.

## Clean-room boundary

A full dependency reinstall in a new machine image was not performed:
`NOT VERIFIED`. The isolated official-Core run, the exact Core import guard,
fresh TemporaryDirectory Full-Core workers and fresh browser contexts provide
partial clean-room evidence. The repository still needs a CI run with a
trusted experimental Core archive before the experimental gate can be marked
CI VERIFIED.

## Beta, HACS and Hassfest

The beta-compatible integration suite was also executed in a separate fresh
Python 3.14.9 environment:

```text
/Users/felixalshut/Documents/ChatGPT/.hkm-beta-314/bin/python scripts/run_beta_integration.py
```

Result: `117 passed, 68 deselected, 19.68s` — `TEST VERIFIED`. The 68 excluded
tests are the `experimental_core` migration tests, which require the separate
pinned Core prototype. The subsequent beta HAP bootstrap, native filter,
reload, and reconnect sequence also passed — `TEST VERIFIED`.

The final GitHub CI run for commit `32ecec3` was `41250127009`: quality,
browser, and beta all completed successfully — `CI VERIFIED`. The separate
experimental Core job was skipped because no trusted archive variables are
configured — `BLOCKED`/not configured. HACS workflow run `41250127197` completed
successfully with both `hacs` and `hassfest` jobs — `CI VERIFIED`.
