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


@pytest.mark.parametrize(
    "value",
    ["+9:30", "０９:３０", "09:3０", " 09:30", "09:30 "],
)
def test_normalize_schedule_time_rejects_non_ascii_or_decorated_values(value):
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


@pytest.mark.parametrize("value", ["/etc/localtime", "../UTC"])
def test_normalize_timezone_rejects_path_like_names(value):
    with pytest.raises(schedule_rules.ScheduleValidationError):
        schedule_rules.normalize_timezone(value)


@pytest.mark.parametrize(
    ("start_time", "frequency", "expected"),
    [
        ("09:07", 1, True),
        ("09:07", 5, False),
        ("09:10", 5, True),
        ("09:20", 10, True),
        ("09:30", 15, True),
        ("09:30", 30, True),
        ("09:00", 60, True),
        ("09:30", 60, False),
    ],
)
def test_is_recurring_boundary(start_time, frequency, expected):
    assert schedule_rules.is_recurring_boundary(start_time, frequency) is expected


def test_opening_trigger_fires_daily_at_start_time():
    trigger = schedule_rules.build_opening_trigger("09:33", "UTC")
    start = datetime(2026, 1, 1, 9, 32, 59, tzinfo=ZoneInfo("UTC"))

    first = trigger.get_next_fire_time(None, start)
    second = trigger.get_next_fire_time(first, first)

    assert first == datetime(2026, 1, 1, 9, 33, tzinfo=ZoneInfo("UTC"))
    assert second == datetime(2026, 1, 2, 9, 33, tzinfo=ZoneInfo("UTC"))


def test_opening_trigger_does_not_catch_up_after_start_second():
    trigger = schedule_rules.build_opening_trigger("09:30", "UTC")
    now = datetime(2026, 1, 1, 9, 30, 1, tzinfo=ZoneInfo("UTC"))

    assert trigger.get_next_fire_time(None, now) == datetime(
        2026, 1, 2, 9, 30, tzinfo=ZoneInfo("UTC")
    )


def test_opening_trigger_skips_nonexistent_spring_forward_time():
    timezone = ZoneInfo("America/New_York")
    trigger = schedule_rules.build_opening_trigger("02:30", "America/New_York")
    start = datetime(2026, 3, 7, 3, 0, tzinfo=timezone)

    assert trigger.get_next_fire_time(None, start) == datetime(
        2026, 3, 9, 2, 30, tzinfo=timezone
    )


def test_opening_trigger_uses_only_first_fall_back_occurrence():
    timezone = ZoneInfo("America/New_York")
    trigger = schedule_rules.build_opening_trigger("01:30", "America/New_York")
    start = datetime(2026, 10, 31, 2, 0, tzinfo=timezone)

    first = trigger.get_next_fire_time(None, start)
    second = trigger.get_next_fire_time(first, first)

    assert first == datetime(2026, 11, 1, 1, 30, tzinfo=timezone, fold=0)
    assert first.fold == 0
    assert second == datetime(2026, 11, 2, 1, 30, tzinfo=timezone)


def test_recurring_trigger_skips_repeated_fall_back_boundaries():
    timezone = ZoneInfo("America/New_York")
    trigger = schedule_rules.build_price_update_trigger(30, "America/New_York")
    start = datetime(2026, 11, 1, 0, 45, tzinfo=timezone)

    first = trigger.get_next_fire_time(None, start)
    second = trigger.get_next_fire_time(first, first)
    third = trigger.get_next_fire_time(second, second)

    assert first == datetime(2026, 11, 1, 1, 0, tzinfo=timezone, fold=0)
    assert second == datetime(2026, 11, 1, 1, 30, tzinfo=timezone, fold=0)
    assert third == datetime(2026, 11, 1, 2, 0, tzinfo=timezone)
    assert first.fold == 0
    assert second.fold == 0


def test_recurring_trigger_skips_nonexistent_spring_forward_boundaries():
    timezone = ZoneInfo("America/New_York")
    trigger = schedule_rules.build_price_update_trigger(30, "America/New_York")
    start = datetime(2026, 3, 8, 1, 45, tzinfo=timezone)

    assert trigger.get_next_fire_time(None, start) == datetime(
        2026, 3, 8, 3, 0, tzinfo=timezone
    )
