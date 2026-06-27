import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import Settings


def make_settings(**overrides):
    return Settings(API_TOKEN="test-token", CHANNEL_ID="test-channel", **overrides)


def test_settings_uses_legacy_timer_interval_when_schedule_frequency_is_absent():
    settings = make_settings(TIMER_INTERVAL=600)

    assert settings.SCHEDULE_FREQUENCY_MINUTES == 10
    assert settings.TIMER_INTERVAL == 600


def test_settings_prefers_schedule_frequency_over_legacy_timer_interval():
    settings = make_settings(
        TIMER_INTERVAL=600,
        SCHEDULE_FREQUENCY_MINUTES=5,
    )

    assert settings.SCHEDULE_FREQUENCY_MINUTES == 5
    assert settings.TIMER_INTERVAL == 300
