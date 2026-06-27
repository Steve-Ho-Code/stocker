from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from src.services import schedule_rules


@pytest.mark.parametrize("frequency", [1, 5, 10, 15, 30, 60])
def test_normalize_frequency_accepts_supported_values(frequency):
    assert schedule_rules.normalize_frequency(str(frequency)) == frequency


@pytest.mark.parametrize("frequency", [0, 2, 7, 1440, "abc"])
def test_normalize_frequency_rejects_unsupported_values(frequency):
    with pytest.raises(schedule_rules.ScheduleValidationError):
        schedule_rules.normalize_frequency(frequency)


@pytest.mark.parametrize(
    ("frequency", "start", "expected"),
    [
        (1, datetime(2026, 1, 1, 0, 7, 30, tzinfo=ZoneInfo("UTC")), datetime(2026, 1, 1, 0, 8, 0, tzinfo=ZoneInfo("UTC"))),
        (5, datetime(2026, 1, 1, 0, 7, 30, tzinfo=ZoneInfo("UTC")), datetime(2026, 1, 1, 0, 10, 0, tzinfo=ZoneInfo("UTC"))),
        (10, datetime(2026, 1, 1, 0, 7, 30, tzinfo=ZoneInfo("UTC")), datetime(2026, 1, 1, 0, 10, 0, tzinfo=ZoneInfo("UTC"))),
        (15, datetime(2026, 1, 1, 0, 7, 30, tzinfo=ZoneInfo("UTC")), datetime(2026, 1, 1, 0, 15, 0, tzinfo=ZoneInfo("UTC"))),
        (30, datetime(2026, 1, 1, 0, 7, 30, tzinfo=ZoneInfo("UTC")), datetime(2026, 1, 1, 0, 30, 0, tzinfo=ZoneInfo("UTC"))),
        (60, datetime(2026, 1, 1, 0, 7, 30, tzinfo=ZoneInfo("UTC")), datetime(2026, 1, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))),
    ],
)
def test_build_price_update_trigger_uses_expected_boundaries(frequency, start, expected):
    trigger = schedule_rules.build_price_update_trigger(frequency, "UTC")

    assert trigger.get_next_fire_time(None, start) == expected


@pytest.mark.parametrize("value", ["00:00", "09:30", "16:00", "23:59"])
def test_normalize_schedule_time_accepts_hh_mm(value):
    assert schedule_rules.normalize_schedule_time(value) == value


@pytest.mark.parametrize("value", ["9:30", "24:00", "12:60", "abcd", "09-30"])
def test_normalize_schedule_time_rejects_invalid_values(value):
    with pytest.raises(schedule_rules.ScheduleValidationError):
        schedule_rules.normalize_schedule_time(value)


def test_validate_schedule_window_rejects_equal_start_and_end():
    with pytest.raises(schedule_rules.ScheduleValidationError):
        schedule_rules.validate_schedule_window("09:30", "09:30")


def test_is_time_within_window_supports_same_day_window():
    assert schedule_rules.is_time_within_window(time(9, 30), "09:30", "16:00")
    assert schedule_rules.is_time_within_window(time(16, 0), "09:30", "16:00")
    assert not schedule_rules.is_time_within_window(time(16, 1), "09:30", "16:00")


def test_is_time_within_window_supports_overnight_window():
    assert schedule_rules.is_time_within_window(time(23, 0), "22:00", "02:00")
    assert schedule_rules.is_time_within_window(time(1, 30), "22:00", "02:00")
    assert not schedule_rules.is_time_within_window(time(3, 0), "22:00", "02:00")


def test_normalize_timezone_accepts_iana_name():
    assert schedule_rules.normalize_timezone("America/New_York") == "America/New_York"


def test_normalize_timezone_rejects_invalid_name():
    with pytest.raises(schedule_rules.ScheduleValidationError):
        schedule_rules.normalize_timezone("New_York")
