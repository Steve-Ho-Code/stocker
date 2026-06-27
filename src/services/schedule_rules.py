from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.triggers.cron import CronTrigger


SUPPORTED_SCHEDULE_FREQUENCIES = (1, 5, 10, 15, 30, 60)
DEFAULT_SCHEDULE_FREQUENCY_MINUTES = 1
DEFAULT_SCHEDULE_START_TIME = "00:00"
DEFAULT_SCHEDULE_END_TIME = "23:59"
DEFAULT_SCHEDULE_TIMEZONE = "America/New_York"


class ScheduleValidationError(ValueError):
    """Raised when schedule configuration is invalid."""


def supported_frequencies_text() -> str:
    return ", ".join(str(value) for value in SUPPORTED_SCHEDULE_FREQUENCIES)


def normalize_frequency(value: int | str) -> int:
    try:
        frequency = int(value)
    except (TypeError, ValueError) as exc:
        raise ScheduleValidationError(
            f"Frequency must be one of: {supported_frequencies_text()} minutes."
        ) from exc

    if frequency not in SUPPORTED_SCHEDULE_FREQUENCIES:
        raise ScheduleValidationError(
            f"Frequency must be one of: {supported_frequencies_text()} minutes."
        )

    return frequency


def normalize_schedule_time(value: str) -> str:
    if not isinstance(value, str):
        raise ScheduleValidationError("Time must use HH:MM format.")

    parts = value.split(":")
    if len(parts) != 2 or len(parts[0]) != 2 or len(parts[1]) != 2:
        raise ScheduleValidationError("Time must use HH:MM format.")

    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError as exc:
        raise ScheduleValidationError("Time must use HH:MM format.") from exc

    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ScheduleValidationError("Time must use HH:MM format.")

    return f"{hour:02d}:{minute:02d}"


def parse_schedule_time(value: str) -> time:
    normalized = normalize_schedule_time(value)
    hour_text, minute_text = normalized.split(":")
    return time(hour=int(hour_text), minute=int(minute_text))


def validate_schedule_window(start_time: str, end_time: str) -> tuple[str, str]:
    normalized_start = normalize_schedule_time(start_time)
    normalized_end = normalize_schedule_time(end_time)

    if normalized_start == normalized_end:
        raise ScheduleValidationError("Start time and end time must be different.")

    return normalized_start, normalized_end


def normalize_timezone(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ScheduleValidationError("Timezone must be a valid IANA timezone name.")

    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ScheduleValidationError("Timezone must be a valid IANA timezone name.") from exc

    return value


def frequency_to_cron_minute(frequency_minutes: int | str) -> str:
    frequency = normalize_frequency(frequency_minutes)
    if frequency == 1:
        return "*"
    if frequency == 60:
        return "0"
    return f"*/{frequency}"


def build_price_update_trigger(
    frequency_minutes: int | str,
    timezone_name: str,
) -> CronTrigger:
    timezone = ZoneInfo(normalize_timezone(timezone_name))
    return CronTrigger(
        minute=frequency_to_cron_minute(frequency_minutes),
        second=0,
        timezone=timezone,
    )


def is_time_within_window(current_time: time, start_time: str, end_time: str) -> bool:
    start = parse_schedule_time(start_time)
    end = parse_schedule_time(end_time)

    if start == end:
        return False

    current = current_time.replace(second=0, microsecond=0)
    if start < end:
        return start <= current <= end

    return current >= start or current <= end


def is_datetime_within_window(
    value: datetime,
    start_time: str,
    end_time: str,
    timezone_name: str,
) -> bool:
    timezone = ZoneInfo(normalize_timezone(timezone_name))
    localized = value.astimezone(timezone)
    return is_time_within_window(localized.time(), start_time, end_time)
