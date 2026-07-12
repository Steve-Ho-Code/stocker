# Spec 007: Advanced Time Management and Scheduling

**Priority:** P0

**Goal:** Replace the fixed-interval price update timer with a timezone-aware schedule that fires once at the start of each active window, then follows exact wall-clock boundaries while the window remains active.

## 1. Core Model

Scheduling has three independently configurable inputs:

- **Frequency:** the interval, in minutes, between recurring wall-clock boundaries.
- **Window:** the inclusive daily time range in which scheduled updates may be sent.
- **Timezone:** the IANA timezone used to interpret the window and all trigger times.

Frequency controls recurring boundaries, the window controls trigger eligibility, and timezone provides the shared wall-clock interpretation. The active-window start has one additional role: it is an opening trigger. If the start time is not already a recurring frequency boundary, the scheduler MUST fire once at the start time and then continue at the next recurring boundary.

Example:

```text
Frequency: 15 minutes
Window: 09:33-16:00
Timezone: America/New_York
Sequence: 09:33, 09:45, 10:00, 10:15, ..., 15:45, 16:00
```

The opening trigger does not shift the recurring boundaries. In the example above, `09:33` does not produce `09:48`, `10:03`, and so on.

## 2. Scope

In scope:

- Exact wall-clock triggering.
- A fixed set of supported update frequencies.
- An inclusive daily active window, including overnight windows.
- Explicit IANA timezone support.
- Redis-backed persistence of scheduling settings.
- Runtime commands for updating scheduling settings.
- Safe removal and recreation of scheduler jobs after configuration changes.

Out of scope:

- Market holiday calendars.
- Exchange-specific early closes.
- Per-user or per-channel schedules.
- Inline keyboard scheduling UI.
- Scheduler health monitoring and alerting.

## 3. Supported Frequencies and Boundaries

`SCHEDULE_FREQUENCY_MINUTES` MUST be one of:

| Frequency | Recurring wall-clock boundaries |
|---|---|
| `1` | Every minute at second `00` |
| `5` | Minutes `00`, `05`, `10`, ..., `55` |
| `10` | Minutes `00`, `10`, `20`, ..., `50` |
| `15` | Minutes `00`, `15`, `30`, and `45` |
| `30` | Minutes `00` and `30` |
| `60` | Minute `00` of every hour |

All other values MUST be rejected. Boundaries are calculated from the top of the hour in the configured timezone, not relative to application startup or the previous fire time.

Examples for a window ending at `16:00`:

| Start | Frequency | Trigger sequence |
|---|---:|---|
| `09:30` | `60` | `09:30`, `10:00`, `11:00`, ..., `15:00`, `16:00` |
| `09:15` | `60` | `09:15`, `10:00`, `11:00`, ..., `15:00`, `16:00` |
| `09:00` | `60` | `09:00`, `10:00`, `11:00`, ..., `15:00`, `16:00` |
| `09:33` | `15` | `09:33`, `09:45`, `10:00`, ..., `15:45`, `16:00` |
| `09:07` | `5` | `09:07`, `09:10`, `09:15`, ..., `15:55`, `16:00` |
| `09:30` | `1` | `09:30`, `09:31`, `09:32`, ..., `15:59`, `16:00` |

Overnight example in `America/New_York`:

```text
Frequency: 60 minutes
Window: 21:30-04:00
Sequence: 21:30, 22:00, 23:00, 00:00, 01:00, 02:00, 03:00, 04:00
```

## 4. Trigger Semantics

For each daily active window while the scheduler is running, subject to the missed-trigger and DST rules below:

1. The first scheduled update MUST occur at `SCHEDULE_START_TIME`.
2. Subsequent updates MUST occur on the next supported wall-clock boundary for the configured frequency.
3. If the start time is already a valid recurring boundary, it MUST produce only one update.
4. A scheduler startup or reschedule MUST NOT cause an arbitrary immediate update. If the current time is after the opening trigger, the next update is the next recurring boundary inside the window.
5. A missed trigger MUST NOT be replayed as a catch-up update. A delayed callback MAY still represent its original occurrence only when it starts within a documented finite misfire grace period, remains inside the active window, and preserves the at-most-once invariant.

A start time is a recurring boundary when:

```text
start_minute % frequency == 0
```

This predicate applies to every supported frequency, including `60`, for which only minute `00` qualifies. Schedule times have minute precision and imply second `00`.

If scheduler startup or rescheduling completes after second `00` of a candidate fire minute, that occurrence is considered missed. The next fire time MUST be strictly later than the registration time; the scheduler MUST NOT send an immediate catch-up update. Any finite scheduler-level misfire grace period MUST be documented and covered by tests without violating the at-most-once invariant in Section 9.

Examples:

```text
Start 09:33, frequency 15 -> first 09:33, then 09:45
Start 09:30, frequency 15 -> one update at 09:30, then 09:45
App starts 10:07 inside a 09:30-16:00 window, frequency 15 -> first update at 10:15
App reschedules at 09:30:01, frequency 15 -> 09:30 is missed; next update at 09:45
```

## 5. Window Rules

Window comparisons MUST use local time in `SCHEDULE_TIMEZONE`, with seconds and microseconds ignored for membership checks.

- **Same-day window (`start < end`):** allow when `start <= t <= end`.
- **Equal bounds (`start == end`):** reject as ambiguous.
- **Overnight window (`start > end`):** allow when `t >= start OR t <= end`.
- **Inclusive end:** a recurring trigger exactly equal to the end time is allowed.

The end time is a filter boundary, not an extra forced trigger. For example, a `09:30-16:05` window with a `60` minute frequency fires at `09:30`, `10:00`, ..., `16:00`; it does not fire again at `16:05`.

Except for the explicit opening trigger at the start time, the window MUST NOT change recurring boundary alignment. A scheduled callback outside the window MUST skip the update and log a message such as `Skipping scheduled price update outside active window`.

Manual `/update` requests MUST remain available outside the active window.

## 6. Timezone Rules

- `SCHEDULE_TIMEZONE` MUST be an IANA timezone name, for example `America/New_York`, `Asia/Hong_Kong`, or `UTC`.
- The default MUST be `America/New_York`.
- Invalid timezone names MUST be rejected during configuration load or command validation.
- The implementation MUST use timezone-aware datetimes and `zoneinfo.ZoneInfo`; it MUST NOT calculate daylight saving offsets manually.
- If an opening time does not exist during a spring-forward transition, the opening trigger for that local calendar date MUST be skipped. It MUST NOT be shifted to another local time.
- If a local time is repeated during a fall-back transition, the opening or recurring trigger MUST fire only for the first occurrence (`fold=0`).
- A repeated local `HH:MM` MUST NOT cause two scheduled updates within the same active-window occurrence.
- APScheduler and `ZoneInfo` MUST be configured or guarded to enforce these policies; library defaults alone are not a product-level guarantee.

## 7. Configuration and Persistence

| Setting | Type | Allowed values | Default |
|---|---|---|---|
| `SCHEDULE_FREQUENCY_MINUTES` | integer | `1`, `5`, `10`, `15`, `30`, `60` | `1` |
| `SCHEDULE_START_TIME` | string | strict `HH:MM` | `00:00` |
| `SCHEDULE_END_TIME` | string | strict `HH:MM` | `23:59` |
| `SCHEDULE_TIMEZONE` | string | valid IANA timezone | `America/New_York` |

Environment variables provide startup defaults. Redis values override those defaults after dynamic settings are loaded.

Dynamic values SHOULD use these Redis keys:

```text
stocker:settings:schedule_frequency_minutes
stocker:settings:schedule_start_time
stocker:settings:schedule_end_time
stocker:settings:schedule_timezone
```

### 7.1 Backward Compatibility

The legacy `TIMER_INTERVAL` and Redis `stocker:settings:timer_interval` values are measured in seconds.

- When `SCHEDULE_FREQUENCY_MINUTES` is absent, convert a legacy value using `frequency = timer_interval // 60`.
- A legacy value MUST be a positive integer, divisible by `60`, and convert to one of the supported frequencies.
- An invalid legacy environment value MUST be rejected during configuration load.
- A corrupted persisted Redis value MUST fall back to the applicable validated default and log a warning.
- A valid new `schedule_frequency_minutes` Redis value MUST take precedence over the legacy Redis key.
- `schedule_frequency_minutes` is the canonical frequency source.
- If only a valid legacy Redis value exists, startup MUST convert it and persist the canonical `schedule_frequency_minutes` key.
- Runtime updates MUST write the canonical key. They MAY dual-write the legacy seconds key for one documented compatibility release, after which legacy writes SHOULD be removed. The rollout plan MUST identify that compatibility release.
- The legacy key remains a read fallback only while the documented migration period is active.

The release implementing Spec 007 is the single compatibility release for legacy `timer_interval` dual-write and read fallback. The next release MUST remove legacy writes and SHOULD remove the fallback after verifying that the canonical key has been populated in deployed Redis instances.

### 7.2 Atomic Runtime Updates

Changes to frequency, window, or timezone MUST behave atomically from the operator's perspective:

1. Validate the complete candidate configuration without changing persisted settings, in-memory settings, or active jobs.
2. Capture the previous validated settings and active job configuration.
3. Persist and activate the candidate settings.
4. Replace the active scheduler jobs.
5. If persistence or job replacement fails, restore the previous persisted settings, in-memory settings, and scheduler jobs.

If compensating rollback also fails, the bot MUST log the full failure, report a degraded scheduling state to the requesting admin, and expose enough effective-state information for recovery. `/config_status` MUST report the active effective settings rather than an unactivated candidate.

## 8. Command Behavior

All commands in this section MUST be restricted to authorized users. Invalid input MUST be rejected with a clear explanation and MUST NOT partially change the active settings.

### 8.1 `/set_timer <N>`

- Sets `SCHEDULE_FREQUENCY_MINUTES`.
- Accepts only `1`, `5`, `10`, `15`, `30`, or `60`.
- Success response:

```text
Timer frequency has been updated to X minute(s).
```

- Invalid input MUST list the supported values.

### 8.2 `/set_schedule_window <HH:MM> <HH:MM>`

- Sets the inclusive daily active window.
- Supports same-day and overnight windows.
- Rejects invalid `HH:MM` values and equal start/end values.
- Success response:

```text
Schedule window has been updated to START-END TIMEZONE.
```

### 8.3 `/set_schedule_timezone <IANA_TIMEZONE>`

- Sets the timezone used by the opening trigger, recurring boundaries, and window checks.
- Success response:

```text
Schedule timezone has been updated to TIMEZONE.
```

### 8.4 `/config_status`

The response MUST include the symbol and all scheduling settings:

```text
Current Bot Configuration:
- Symbol: <VALUE>
- Timer Frequency: <VALUE> minute(s)
- Schedule Window: <START>-<END>
- Schedule Timezone: <IANA_TIMEZONE>
```

## 9. Scheduler Architecture

The reference design uses up to two named jobs:

| Job name | Purpose |
|---|---|
| `price_update_open` | Daily opening trigger at `SCHEDULE_START_TIME` when the start is not already a recurring boundary |
| `price_update_cron` | Recurring wall-clock boundary trigger for the configured frequency |

An implementation SHOULD use this two-job design because it maps directly to the opening and recurring behaviors. A behaviorally equivalent composite trigger MAY be used if it satisfies every scheduling, replacement, DST, and at-most-once test in this spec.

`price_update_open` is a daily timezone-aware trigger, not a process-lifetime one-shot. It MUST be omitted when the start time is already a valid `price_update_cron` boundary, preventing duplicate updates.

`schedule_price_update()` MUST:

1. Validate the complete candidate configuration.
2. Build all candidate triggers without changing the active jobs.
3. Capture enough information to restore the current validated job configuration.
4. Remove every scheduler job owned by the price-update scheduling service, including `price_update_open`, `price_update_cron`, and legacy `price_update` jobs.
5. Register either:
   - The reference jobs, omitting `price_update_open` when the configured start is already a recurring boundary and adding `price_update_cron` with a timezone-aware cron trigger; or
   - One behaviorally equivalent composite trigger owned by the same service.
6. Ensure every scheduled callback applies the active-window and DST duplicate checks before sending an update.
7. Restore the previous job configuration if any candidate job cannot be registered.

`reschedule_price_update()` MUST remove and recreate the full job set. Repeated configuration changes MUST NOT create duplicate jobs.

Scheduling and validation logic SHOULD remain separate from Telegram command handlers so every configuration path uses the same behavior.

For any configured timezone-local date and `HH:MM`, the scheduler MUST send at most one scheduled price update for the same active-window occurrence. This send-level invariant applies even during rescheduling races, scheduler misfires, process recovery, and fall-back DST transitions; merely avoiding duplicate registered jobs is not sufficient.

## 10. Error Handling

| Scenario | Required action |
|---|---|
| Unsupported frequency, such as `7` | Reject and list supported values |
| Invalid time, such as `25:00` | Reject with an `HH:MM` explanation |
| Invalid timezone | Reject and require a valid IANA name |
| Equal start and end | Reject because the window is ambiguous |
| Corrupted persisted settings | Fall back to validated defaults and log a warning |
| Persistence or reschedule failure | Restore the previous settings and jobs, log the exception, and report the failure to the requesting admin |
| Compensating rollback failure | Report a degraded scheduling state and expose the active effective state for recovery |
| Scheduled callback outside the window | Skip and log the reason |
| Manual `/update` outside the window | Allow the update |

## 11. Test Requirements

Unit and handler tests MUST cover:

- Accepting `1`, `5`, `10`, `15`, `30`, and `60`, and rejecting every unsupported value tested.
- Strict `HH:MM` parsing and rejection of equal window bounds.
- Same-day, inclusive-end, and overnight window membership.
- Valid and invalid IANA timezone names.
- The recurring boundaries for every supported frequency.
- An off-boundary start firing once at the opening time and then at the next recurring boundary.
- An on-boundary start producing only one update.
- Startup or reschedule inside a window selecting the next boundary without an immediate catch-up update.
- Rescheduling after second `00` of a boundary minute treating that boundary as missed.
- Daily recurrence of the opening trigger.
- Skipping a nonexistent spring-forward opening time without shifting it.
- Sending only once at the first occurrence of a repeated fall-back local time.
- Replacement of opening, recurring, and legacy jobs without duplicates.
- A partial candidate-job registration failure restoring the previous complete job set.
- Persistence, reschedule, and compensating-rollback failure paths.
- The send-level at-most-once invariant during rescheduling races and scheduler misfires.
- `/set_timer`, `/set_schedule_window`, `/set_schedule_timezone`, and `/config_status` responses and authorization.
- Legacy seconds-to-minutes conversion, precedence, rejection, and corrupted Redis fallback behavior.
- Manual `/update` remaining independent of the active window.

## 12. Completion Criteria

This feature is complete when:

- Each existing, non-missed daily opening time produces exactly one update when the scheduler is running.
- Subsequent scheduled updates use exact wall-clock boundaries for all supported frequencies.
- No timezone-local date and `HH:MM` receives more than one scheduled update for the same active-window occurrence.
- Scheduled updates outside the inclusive same-day or overnight window are skipped.
- All schedule calculations use the configured IANA timezone.
- Scheduling settings survive restart through Redis-backed persistence.
- Authorized users can update frequency, window, and timezone at runtime.
- Failed configuration changes restore the previous effective settings and job configuration.
- Rescheduling cannot leave duplicate or legacy jobs active.
- `/config_status` displays all effective schedule settings.
- Manual `/update` behavior remains unchanged.
- Relevant automated tests pass.
