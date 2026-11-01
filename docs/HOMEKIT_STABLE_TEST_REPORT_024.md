# HomeKit Manager 0.10.24 – Stable Test Report

## Local evidence

| Gate | Result |
|---|---|
| Reproducible release build, two runs | TEST VERIFIED |
| Release archive contents | TEST VERIFIED |
| Frontend syntax check | TEST VERIFIED |
| Frontend panel behavior test | TEST VERIFIED |
| Existing Manager unit/protocol subset | TEST VERIFIED in prior 0.10.23 run |
| Full local stable pytest suite | BLOCKED by Python 3.14 import/plugin environment |
| Official Core full integration suite | NOT VERIFIED locally in this sprint |
| Experimental Core suite | Separate workflow; not Stable scope |

## CI evidence inherited from 0.10.23

The 0.10.23 CI run had successful Quality and Browser jobs, but the Beta Core
and experimental Core jobs failed. HACS and Hassfest passed in their separate
workflow. Those results are not a complete 0.10.24 Stable release gate.

The 0.10.24 branch therefore requires a fresh Stable CI run after push. The
Stable workflow intentionally excludes experimental Core jobs.
