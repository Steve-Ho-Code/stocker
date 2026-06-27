# Spec 007: Advanced Time Management and Scheduling

**Goal:** Replace the current fixed-interval price update timer with a schedule-aware mechanism that can trigger updates on exact time boundaries, respect configured active hours, and evaluate all scheduling rules in an explicit market timezone.

## 1. Rationale

The bot currently schedules price updates with a simple repeating interval. This is enough for basic polling, but it does not guarantee that updates happen at predictable wall-clock times. For financial market monitoring, predictable timing matters because users expect updates near exact market-relevant boundaries, such as every 10 minutes or at the top of each hour.

The scheduler should also avoid sending updates outside the desired daily window. This reduces unnecessary external API usage, prevents noisy channel updates during inactive hours, and makes the bot behavior easier to reason about during daylight saving time changes.

## 2. Scope

This spec covers the P0 "Advanced Time Management & Scheduling" roadmap item.

In scope:

- Exact time triggering.
- Configurable update frequency.
- Daily start and end time configuration.
- Explicit timezone support.
- Persistence of scheduling settings.
- Rescheduling the active background job when scheduling settings change.

Out of scope:

- Full market holiday calendar support.
- Exchange-specific early close detection.
- Per-user or per-channel schedules.
- Inline keyboard UI for scheduling settings.
- Monitoring or alerting for scheduler health.

## 3. Functional Requirements

### 3.1 Exact Time Triggering

- The scheduler MUST trigger price update attempts on wall-clock boundaries instead of drifting relative to application startup time.
- Supported frequencies MUST align to the following boundaries:
    - Every 1 minute: trigger at second `00` of each minute.
    - Every 5 minutes: trigger when the minute is divisible by `5`.
    - Every 10 minutes: trigger when the minute is divisible by `10`.
    - Every 15 minutes: trigger when the minute is `00`, `15`, `30`, or `45`.
    - Every 30 minutes: trigger when the minute is `00` or `30`.
    - Every 60 minutes: trigger when the minute is `00`.
- The scheduled job MUST not use `first=0` behavior that sends an immediate startup update unless the current time is already a valid schedule boundary and inside the active daily window.
- The implementation SHOULD use APScheduler cron-style scheduling, such as `CronTrigger`, because the project already depends on APScheduler through `python-telegram-bot` job queue support.

### 3.2 Configurable Frequency

- Authorized users MUST be able to configure the update frequency.
- The supported frequency values MUST be:
    - `1` minute.
    - `5` minutes.
    - `10` minutes.
    - `15` minutes.
    - `30` minutes.
    - `60` minutes.
- Unsupported values MUST be rejected with a clear error message.
- The existing `/set_timer` command MAY be reused for this setting, but its validation MUST change from "any positive number up to `MAX_TIMER_INTERVAL`" to the supported frequency set above.
- The bot MUST persist the selected frequency so the setting survives application restart.
- The bot MUST reschedule the active price update job immediately after the frequency is changed.

### 3.3 Daily Start and End Time

- The bot MUST support a daily active window for scheduled price updates.
- The active window MUST be defined by:
    - `SCHEDULE_START_TIME`, formatted as `HH:MM`.
    - `SCHEDULE_END_TIME`, formatted as `HH:MM`.
- Times MUST be interpreted in the configured schedule timezone.
- Scheduled price update jobs MUST only send updates when the current local time is inside the active window.
- The default active window SHOULD be broad enough to preserve existing behavior unless explicitly configured.
- Invalid time strings MUST be rejected with a clear error message.
- If the start time equals the end time, the configuration MUST be rejected to avoid ambiguous behavior.
- If the start time is later than the end time, the schedule MAY support an overnight window, but the chosen behavior MUST be documented and covered by tests.

### 3.4 Timezone Support

- The scheduler MUST use an explicit timezone value.
- The default timezone SHOULD be `America/New_York` because the bot examples and roadmap focus on US market assets.
- The timezone value MUST use an IANA timezone name, such as `America/New_York`, `Asia/Hong_Kong`, or `UTC`.
- Invalid timezone names MUST be rejected at configuration load time or update time.
- Daylight saving time transitions MUST be handled by the timezone-aware scheduler rather than by manual offset calculations.

## 4. Configuration

The following settings SHOULD be added or formalized:

- `SCHEDULE_FREQUENCY_MINUTES`: integer, one of `1`, `5`, `10`, `15`, `30`, or `60`.
- `SCHEDULE_START_TIME`: string in `HH:MM` format.
- `SCHEDULE_END_TIME`: string in `HH:MM` format.
- `SCHEDULE_TIMEZONE`: IANA timezone string.

Dynamic scheduling settings SHOULD be stored in Redis, consistent with the existing `SYMBOL` and `TIMER_INTERVAL` dynamic settings.

Environment variables SHOULD provide startup defaults. Redis values SHOULD override environment defaults after dynamic settings are loaded.

## 5. Command Behavior

### 5.1 `/set_timer`

- `/set_timer <MINUTES>` MUST continue to be restricted to authorized users.
- Valid examples:
    - `/set_timer 1`
    - `/set_timer 5`
    - `/set_timer 10`
    - `/set_timer 15`
    - `/set_timer 30`
    - `/set_timer 60`
- Invalid examples:
    - `/set_timer 7`
    - `/set_timer 1440`
    - `/set_timer abc`
- On success, the bot MUST confirm the new schedule frequency.
- On failure, the bot MUST list the supported values.

### 5.2 Schedule Window Configuration

The implementation SHOULD introduce admin-only commands for updating the daily active window and timezone, unless a simpler existing configuration path is chosen.

Suggested commands:

- `/set_schedule_window <START_HH:MM> <END_HH:MM>`
- `/set_schedule_timezone <IANA_TIMEZONE>`

The final command names MAY differ, but the implemented UX MUST allow authorized users to update these settings without editing server files.

### 5.3 `/config_status`

The `/config_status` command MUST include the active scheduling settings after this feature is implemented:

```text
Current Bot Configuration:
- Symbol: <VALUE>
- Timer Frequency: <VALUE> minute(s)
- Schedule Window: <START_HH:MM>-<END_HH:MM>
- Schedule Timezone: <IANA_TIMEZONE>
```

## 6. Technical Requirements

- Scheduling logic SHOULD be separated from Telegram command handlers to avoid duplicating reschedule behavior across direct command and conversation flows.
- The job name SHOULD remain stable, for example `price_update`, so existing job replacement logic remains simple.
- Rescheduling MUST remove any existing active `price_update` job before registering the new schedule.
- The scheduler MUST not create duplicate price update jobs after repeated configuration changes.
- Manual `/update` behavior MUST remain unchanged and MUST continue to work outside the scheduled active window.
- External provider selection and price formatting MUST remain unchanged.

## 7. Error Handling

- Invalid frequency values MUST be rejected before changing persisted settings.
- Invalid time values MUST be rejected before changing persisted settings.
- Invalid timezone values MUST be rejected before changing persisted settings.
- If rescheduling fails after settings are persisted, the error MUST be logged and the bot SHOULD report the failure to the requesting admin.
- If the app starts with invalid persisted scheduling settings, it SHOULD fall back to safe defaults and log the invalid values.

## 8. Test Requirements

- Unit tests MUST cover frequency validation for valid and invalid values.
- Unit tests MUST cover `HH:MM` time parsing and invalid time strings.
- Unit tests MUST cover timezone validation.
- Unit tests MUST verify the generated schedule boundaries for `1`, `5`, `10`, `15`, `30`, and `60` minute frequencies.
- Handler tests MUST verify `/set_timer` accepts only supported values and reports errors for unsupported values.
- Handler tests SHOULD verify schedule window and timezone commands if those commands are implemented.
- Tests MUST verify that rescheduling replaces the existing job instead of adding duplicates.

## 9. Validation

This feature is complete when:

- Scheduled updates fire on exact wall-clock boundaries for all supported frequencies.
- Scheduled updates are skipped outside the configured daily active window.
- The active timezone is explicit and uses an IANA timezone name.
- Scheduling settings survive application restart through Redis-backed dynamic settings.
- Admin commands can update the supported scheduling settings.
- `/config_status` displays the current scheduling settings.
- Existing manual update behavior still works.
- Relevant automated tests pass.
