# 0.10.32-rc.2 – Native Operation Crash Matrix

The matrix uses isolated Home Assistant Core 2026.10.4 processes with two
paired HAP test bridges and real `SIGKILL` termination. Each row starts from a
fresh temporary instance, records the requested fault point, restarts Core,
loads the persisted journal, and performs read-only reconciliation.

## Apply

| Fault point | Process exit | Recovery process | Result | Journal |
|---|---:|---:|---|---|
| `before_lock` | 137 | 0 | `not_applied` | `not_applied/verified` |
| `after_confirmation` | 137 | 0 | `not_applied` | `not_applied/verified` |
| `after_write_grant_check` | 137 | 0 | `not_applied` | `not_applied/verified` |
| `after_lock` | 137 | 0 | `not_applied` | `not_applied/verified` |
| `before_apply_journal` | 137 | 0 | `not_applied` | `not_applied/verified` |
| `after_apply_journal_checkpoint` | 137 | 0 | `not_applied` | `not_applied/verified` |
| `before_native_operation_journal` | 137 | 0 | `not_applied` | `not_applied/verified` |
| `after_native_operation_journal` | 137 | 0 | `not_applied` | `not_applied/verified` |
| `before_native_options` | 137 | 0 | `not_applied` | `not_applied/verified` |
| `after_native_options` | 137 | 0 | `not_applied` | `not_applied/verified` |
| `before_reload` | 137 | 0 | `not_applied` | `not_applied/verified` |
| `after_reload` | 137 | 0 | `not_applied` | `not_applied/verified` |
| `after_native_verification` | 137 | 0 | `verified_options` | `verified/verified` |
| `before_apply_journal_final` | 137 | 0 | `verified_options` | `verified/verified` |
| `after_apply_journal` | 137 | 0 | `verified_options` | `verified/verified` |

## Rollback

| Fault point | Process exit | Recovery process | Result | Journal |
|---|---:|---:|---|---|
| `rollback_before_lock` | 137 | 0 | `verified_options` | `verified/verified` |
| `rollback_after_confirmation` | 137 | 0 | `verified_options` | `verified/verified` |
| `rollback_after_write_grant_check` | 137 | 0 | `verified_options` | `verified/verified` |
| `rollback_after_lock` | 137 | 0 | `verified_options` | `verified/verified` |
| `rollback_before_journal` | 137 | 0 | `verified_options` | `verified/verified` |
| `rollback_after_journal_checkpoint` | 137 | 0 | `rollback_not_applied` | `rollback_unknown/verified` |
| `rollback_before_native_options` | 137 | 0 | `rollback_not_applied` | `rollback_unknown/verified` |
| `rollback_after_native_options` | 137 | 0 | `rollback_not_applied` | `rollback_unknown/verified` |
| `rollback_before_reload` | 137 | 0 | `rollback_not_applied` | `rollback_unknown/verified` |
| `rollback_after_reload` | 137 | 0 | `rollback_not_applied` | `rollback_unknown/verified` |
| `after_rollback_write` | 137 | 0 | `rollback_verified` | `rolled_back/verified` |
| `before_rollback_verification` | 137 | 0 | `rollback_verified` | `rolled_back/verified` |
| `after_rollback_verification` | 137 | 0 | `rollback_verified` | `rolled_back/verified` |
| `rollback_before_journal_final` | 137 | 0 | `rollback_verified` | `rolled_back/verified` |
| `rollback_after_journal` | 137 | 0 | `rollback_verified` | `rolled_back/verified` |

## Interpretation

The durable Config Entry flush is completed before a mutation is considered
verified. Therefore a crash after the native write but before the final
journal checkpoint is classified from the persisted native state rather than
replayed. Unknown or contradictory states remain blocked and require explicit
administrator recovery. The same 15-point Apply and 15-point Rollback matrix
was also executed with Core 2026.11.0b0 in an isolated beta environment. All
beta rows produced the same exit/recovery classes and passed their
journal-integrity checks. The GitHub beta workflow additionally passed its
isolated integration and HAP Apply/Reload/Reconnect suite.
