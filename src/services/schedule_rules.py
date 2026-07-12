import re
from datetime import datetime, time, timezone as datetime_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.triggers.cron import CronTrigger


SUPPORTED_SCHEDULE_FREQUENCIES = (1, 5, 10, 15, 30, 60)
DEFAULT_SCHEDULE_FREQUENCY_MINUTES = 1
DEFAULT_SCHEDULE_START_TIME = "00:00"
DEFAULT_SCHEDULE_END_TIME = "23:59"
DEFAULT_SCHEDULE_TIMEZONE = "America/New_York"


class ScheduleValidationError(ValueError):
    """Raised when schedule configuration is invalid."""


class DSTSafeCronTrigger(CronTrigger):
    """Cron trigger that skips nonexistent and repeated local wall-clock times."""

    @staticmethod
    def _wall_clock_components(value: datetime) -> tuple[int, ...]:
        return (
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
            value.microsecond,
        )

    def _is_valid_local_occurrence(self, candidate: datetime) -> bool:
        localized = candidate.astimezone(self.timezone)
        if localized.fold != 0:
            return False

        round_tripped = localized.astimezone(datetime_timezone.utc).astimezone(
            self.timezone
        )
        return (
            self._wall_clock_components(round_tripped)
            == self._wall_clock_components(localized)
            and round_tripped.fold == localized.fold
        )

    def get_next_fire_time(
        self,
        previous_fire_time: datetime | None,
        now: datetime,
    ) -> datetime | None:
        candidate = super().get_next_fire_time(previous_fire_time, now)
        while candidate is not None and not self._is_valid_local_occurrence(candidate):
            candidate = super().get_next_fire_time(candidate, candidate)
        return candidate


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
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{2}:[0-9]{2}", value) is None:
        raise ScheduleValidationError("Time must use HH:MM format.")

    hour_text, minute_text = value.split(":")
    try:
        hour = int(hour_text)
        minute = int(minute_text)
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
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ScheduleValidationError("Timezone must be a valid IANA timezone name.") from exc

    return value


def frequency_to_cron_minute(frequency_minutes: int | str) -> str:
    frequency = normalize_frequency(frequency_minutes)
    if frequency == 1:
        return "*"
    if frequency == 60:
        return "0"
    return f"*/{frequency}"


def is_recurring_boundary(
    schedule_time: str,
    frequency_minutes: int | str,
) -> bool:
    frequency = normalize_frequency(frequency_minutes)
    minute = parse_schedule_time(schedule_time).minute
    return minute % frequency == 0


def build_price_update_trigger(
    frequency_minutes: int | str,
    timezone_name: str,
) -> DSTSafeCronTrigger:
    timezone = ZoneInfo(normalize_timezone(timezone_name))
    return DSTSafeCronTrigger(
        minute=frequency_to_cron_minute(frequency_minutes),
        second=0,
        timezone=timezone,
    )


def build_opening_trigger(
    start_time: str,
    timezone_name: str,
) -> DSTSafeCronTrigger:
    opening_time = parse_schedule_time(start_time)
    timezone = ZoneInfo(normalize_timezone(timezone_name))
    return DSTSafeCronTrigger(
        hour=opening_time.hour,
        minute=opening_time.minute,
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
