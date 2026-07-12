import os
import sys
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import Settings
from src import config
from src.services import scheduler_service


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


class FakeConfigRedis:
    def __init__(self, data=None, concurrent_canonical=None):
        self.data = dict(data or {})
        self.concurrent_canonical = concurrent_canonical
        self.set_calls = []

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, **kwargs):
        self.set_calls.append((key, value, kwargs))
        if kwargs.get("nx") and self.concurrent_canonical is not None:
            self.data[key] = str(self.concurrent_canonical)
            self.concurrent_canonical = None
            return None
        if kwargs.get("nx") and key in self.data:
            return None
        self.data[key] = str(value)
        return True


@pytest.mark.asyncio
async def test_get_dynamic_settings_migrates_valid_legacy_frequency(mocker):
    redis = FakeConfigRedis({"stocker:settings:timer_interval": "900"})
    mocker.patch.object(config, "redis_client", redis)

    result = await config.get_dynamic_settings()

    assert result["SCHEDULE_FREQUENCY_MINUTES"] == 15
    assert redis.set_calls == [
        ("stocker:settings:schedule_frequency_minutes", 15, {"nx": True})
    ]


@pytest.mark.asyncio
async def test_legacy_migration_does_not_overwrite_concurrent_canonical_update(
    mocker,
):
    redis = FakeConfigRedis(
        {"stocker:settings:timer_interval": "900"},
        concurrent_canonical="5",
    )
    mocker.patch.object(config, "redis_client", redis)

    result = await config.get_dynamic_settings()

    assert result["SCHEDULE_FREQUENCY_MINUTES"] == 5
    assert redis.data["stocker:settings:schedule_frequency_minutes"] == "5"
    assert redis.set_calls == [
        ("stocker:settings:schedule_frequency_minutes", 15, {"nx": True})
    ]


@pytest.mark.asyncio
async def test_corrupted_persisted_window_falls_back_to_default_pair(mocker):
    redis = FakeConfigRedis(
        {
            "stocker:settings:schedule_start_time": "invalid",
            "stocker:settings:schedule_end_time": "18:00",
        }
    )
    mocker.patch.object(config, "redis_client", redis)
    mocker.patch.object(config.settings, "SCHEDULE_START_TIME", "00:00")
    mocker.patch.object(config.settings, "SCHEDULE_END_TIME", "23:59")

    result = await config.get_dynamic_settings()

    assert result["SCHEDULE_START_TIME"] == "00:00"
    assert result["SCHEDULE_END_TIME"] == "23:59"


def test_settings_rejects_invalid_legacy_timer_interval():
    with pytest.raises(ValidationError):
        make_settings(TIMER_INTERVAL=420)


@pytest.mark.asyncio
async def test_canonical_redis_frequency_takes_precedence_over_legacy(mocker):
    redis = FakeConfigRedis(
        {
            "stocker:settings:schedule_frequency_minutes": "5",
            "stocker:settings:timer_interval": "900",
        }
    )
    mocker.patch.object(config, "redis_client", redis)

    result = await config.get_dynamic_settings()

    assert result["SCHEDULE_FREQUENCY_MINUTES"] == 5
    assert redis.set_calls == []


@pytest.mark.asyncio
async def test_corrupted_legacy_redis_frequency_uses_default_without_migration(
    mocker,
    caplog,
):
    redis = FakeConfigRedis({"stocker:settings:timer_interval": "421"})
    mocker.patch.object(config, "redis_client", redis)
    mocker.patch.object(config.settings, "SCHEDULE_FREQUENCY_MINUTES", 1)

    result = await config.get_dynamic_settings()

    assert result["SCHEDULE_FREQUENCY_MINUTES"] == 1
    assert redis.set_calls == []
    assert "Invalid persisted timer_interval" in caplog.text


@pytest.mark.asyncio
async def test_corrupted_canonical_frequency_and_timezone_use_defaults(
    mocker,
    caplog,
):
    redis = FakeConfigRedis(
        {
            "stocker:settings:schedule_frequency_minutes": "7",
            "stocker:settings:schedule_timezone": "Not/A_Zone",
        }
    )
    mocker.patch.object(config, "redis_client", redis)
    mocker.patch.object(config.settings, "SCHEDULE_FREQUENCY_MINUTES", 1)
    mocker.patch.object(config.settings, "SCHEDULE_TIMEZONE", "UTC")

    result = await config.get_dynamic_settings()

    assert result["SCHEDULE_FREQUENCY_MINUTES"] == 1
    assert result["SCHEDULE_TIMEZONE"] == "UTC"
    assert "Invalid persisted schedule_frequency_minutes" in caplog.text
    assert "Invalid persisted schedule_timezone" in caplog.text


@pytest.mark.asyncio
async def test_startup_load_activates_persisted_schedule_before_job_registration(
    mocker,
):
    redis = FakeConfigRedis(
        {
            "stocker:settings:symbol": "SPY",
            "stocker:settings:schedule_frequency_minutes": "15",
            "stocker:settings:schedule_start_time": "09:33",
            "stocker:settings:schedule_end_time": "16:00",
            "stocker:settings:schedule_timezone": "UTC",
        }
    )
    mocker.patch.object(config, "redis_client", redis)
    mocker.patch.object(config.settings, "SCHEDULE_FREQUENCY_MINUTES", 1)
    mocker.patch.object(config.settings, "TIMER_INTERVAL", 60)
    mocker.patch.object(config.settings, "SCHEDULE_START_TIME", "00:00")
    mocker.patch.object(config.settings, "SCHEDULE_END_TIME", "23:59")
    mocker.patch.object(config.settings, "SCHEDULE_TIMEZONE", "America/New_York")
    job_queue = MagicMock()
    job_queue.get_jobs_by_name.return_value = []
    job_queue.run_custom.side_effect = lambda *args, **kwargs: MagicMock()

    await config.load_settings_from_redis()
    scheduler_service.schedule_price_update(job_queue, lambda context: None)

    assert scheduler_service.current_schedule_config() == scheduler_service.ScheduleConfig(
        15,
        "09:33",
        "16:00",
        "UTC",
    )
    assert [call.kwargs["name"] for call in job_queue.run_custom.call_args_list] == [
        scheduler_service.PRICE_UPDATE_OPEN_JOB_NAME,
        scheduler_service.PRICE_UPDATE_CRON_JOB_NAME,
    ]
