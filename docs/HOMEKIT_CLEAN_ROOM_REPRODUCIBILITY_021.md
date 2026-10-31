# Clean-Room Reproducibility 0.10.21

## Intended build

The CI workflow creates a new Core checkout from the official remote at the
exact base commit, applies the reviewed patch, creates a fresh Python runtime,
and starts fresh pytest processes. It does not use a moving Core branch or an
archive URL supplied through repository variables.

## Local execution

The local patch verification used an isolated temporary Git worktree at the
official base commit and produced the exact target tree. This validates patch
application and provenance, but it shares the existing local Core object store
and is therefore not a complete clean-room installation.

An attempted network clone was stopped by the host filesystem with:

```text
fatal: write error: No space left on device
fatal: fetch-pack: invalid index-pack output
```

Consequently, a full local fresh-clone plus fresh dependency installation is
NOT VERIFIED on the macOS host. No product or persistent Home Assistant data
was involved.

## Reproduction inputs

| Input | Value |
|---|---|
| OS tested locally | macOS host |
| Python | 3.14.9 |
| pytest | 9.0.3 |
| Core version | 2026.10.4 |
| Core base | `357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b` |
| Patch SHA-256 | `ad8a0a1166d634c829978fb35be35b7894b9ea136011023e76e1fbb29dd23537` |
| Target tree | `8419f460ab542256cbee6f8031a874e6f43608a4` |
| Experimental result | `68 passed, 0 skipped` |

## GitHub clean-room result

The GitHub Actions `experimental-core-native` job in run `41253834835` created
the fresh runner checkout, fetched the exact base commit, applied the verified
patch, ran the guard and experimental suite, and uploaded the evidence artifact.
The job completed successfully. This is CI VERIFIED for the tested GitHub
Actions Ubuntu environment; it is not a claim of platform-independent
reproducibility.
