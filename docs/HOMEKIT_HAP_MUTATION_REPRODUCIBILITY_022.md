# 0.10.22 Reproduction Instructions

All commands below use the isolated experimental Core checkout and a temporary
configuration. They do not access a productive Home Assistant directory.

## Environment

- Manager checkout: `/Users/felixalshut/Documents/ChatGPT/homeassistant-homekit-manager`
- Core checkout: `/Users/felixalshut/Documents/ChatGPT/homeassistant-core-0.10.14-poc`
- Core version: `2026.10.4`
- Core base: `357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b`
- Experimental Core commit: `a4ee64492c9e6d58ed58bf23e7eeccf58c382aba`
- Experimental Core tree: `2e0df24b8b73cd4152e3c7e405038a8e34b230e2`
- Patch: `.ci/experimental-core/hkm-core-2026.10.4-0.10.22.patch`
- Patch SHA-256: `8497b9bd047284bfdc8cc90678fa277c6a02daadcfc3a4c2a053ac2f6abccc23`

## Full mutation campaign

```sh
export CORE_ROOT=/Users/felixalshut/Documents/ChatGPT/homeassistant-core-0.10.14-poc
export HKM_VENV=/Users/felixalshut/Documents/ChatGPT/.hkm-core-314
export PYTHONPATH="$CORE_ROOT:/Users/felixalshut/Documents/ChatGPT/homeassistant-homekit-manager"
"$HKM_VENV/bin/python" -m pytest -q \
  tests/integration/test_core_hap_mutation_security_022.py \
  --disable-warnings --maxfail=1
```

Expected local result:

```text
11 passed, 1 warning in 156.96s
```

## Existing regression

```sh
"$HKM_VENV/bin/python" -m pytest -q \
  tests/integration/test_core_multibridge_migration_015.py \
  --disable-warnings --maxfail=1
```

Expected local result:

```text
7 passed, 1 warning in 31.15s
```

The warning is the known optional TurboJPEG library warning from the isolated
environment; it does not alter HAP pairing or assertions.

## Patch verification

The CI gate must begin from the exact official base, verify the manifest and
SHA-256, apply the patch with `git apply --check`, verify changed files and the
resulting tree, and only then collect experimental tests. A missing patch,
wrong tree, wrong Core import, empty collection, or skipped mandatory test is a
failed gate rather than a pass.
