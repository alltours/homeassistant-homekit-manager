# HomeKit Core Patch Provenance 0.10.21

## Reviewed source state

The local Core checkout was clean before export. The official `2026.10.4` tag
resolved to:

```text
357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b
```

The experimental checkout ended at:

```text
c04fa739c790169977447b0373e5c26e7e334021
```

The diff contains these four paths:

```text
homeassistant/components/homekit/__init__.py
homeassistant/components/homekit/migration.py
homeassistant/config_entries.py
tests/components/homekit/test_migration.py
```

The resulting patch has SHA-256:

```text
ad8a0a1166d634c829978fb35be35b7894b9ea136011023e76e1fbb29dd23537
```

The target tree is:

```text
8419f460ab542256cbee6f8031a874e6f43608a4
```

These values are stored in `.ci/experimental-core/manifest.json` and are
checked by `scripts/verify_experimental_core_patch.py`.

## Reproduction

```text
git clone --filter=blob:none --no-checkout https://github.com/home-assistant/core.git "$CORE_ROOT"
git -C "$CORE_ROOT" fetch --depth=1 origin 357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b
git -C "$CORE_ROOT" checkout --detach 357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b
python scripts/verify_experimental_core_patch.py \
  --core-root "$CORE_ROOT" \
  --manifest .ci/experimental-core/manifest.json \
  --evidence "$ARTIFACTS/patch-verification.json"
```

The verifier rejects a dirty checkout, a wrong base HEAD, a missing or
tampered patch, an unexpected changed-file set, or a tree hash different from
the reviewed target. It applies `git apply --check` before the actual apply.

## Commit chain

The eight experimental commits after the official tag are:

```text
9bf140eeffae9fd1d145f2770590bce2e86602e7 Add experimental Core-owned HomeKit migration boundary
9dcdfb0ed71e06ab14134b96716a5ceccfa24365 Fail closed when recovered HAP MAC is unavailable
8282b56ca20b5f9302221801c7dbcf3cbf202c7d test(homekit): inject isolated recovery crash point
ba7e523872fae6672409fdb4b3646e07ed15a356 feat: fail closed on corrupt HomeKit migration journal
5a1d8b1cefcdf35e5db02f36928ae334582f9094 feat: add Core-owned HomeKit transaction protocol
332819d18d1160d3b14e580ad593ea3d93fab1c3 fix: make migration journal writes atomic
5a7b4ef42cda1b79ec5855be5f365d4d647b35c4 feat: add Core-owned HomeKit rollback executor
c04fa739c790169977447b0373e5c26e7e334021 fix: harden homekit migration journal validation
```

The official Core remote is not modified or pushed by this work.
