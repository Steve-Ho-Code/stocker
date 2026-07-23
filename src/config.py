import logging

import redis.asyncio as redis
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field, field_validator, model_validator

from .services import schedule_rules


logger = logging.getLogger(__name__)


def _frequency_from_timer_interval(value: str | int) -> int:
    try:
        seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise schedule_rules.ScheduleValidationError(
            "Timer interval must be a number of seconds."
        ) from exc

    if seconds <= 0 or seconds % 60 != 0:
        raise schedule_rules.ScheduleValidationError(
            "Timer interval must be a positive whole number of minutes."
        )

    return schedule_rules.normalize_frequency(seconds // 60)


class Settings(BaseSettings):
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/stocker.log"
    LOG_MAX_BYTES: int = Field(default=10 * 1024 * 1024, gt=0)
    LOG_BACKUP_COUNT: int = Field(default=5, gt=0)

    # Telegram Bot Configuration
    API_TOKEN: str
    CHANNEL_ID: str
    SUPER_ADMIN_TELEGRAM_ID: int = 0

    # Dynamic settings that can be changed at runtime
    MAX_TIMER_INTERVAL: int = 1440  # in minutes
    SYMBOL: str = "VOO"  # Default symbol
    TIMER_INTERVAL: int = 60  # Backward-compatible interval in seconds
    SCHEDULE_FREQUENCY_MINUTES: int = schedule_rules.DEFAULT_SCHEDULE_FREQUENCY_MINUTES
    SCHEDULE_START_TIME: str = schedule_rules.DEFAULT_SCHEDULE_START_TIME
    SCHEDULE_END_TIME: str = schedule_rules.DEFAULT_SCHEDULE_END_TIME
    SCHEDULE_TIMEZONE: str = schedule_rules.DEFAULT_SCHEDULE_TIMEZONE

    # Redis Configuration
    REDIS_URL: str = "redis://localhost"

    # Database Configuration
    DATABASE_URL: str = "postgresql://user:password@localhost/stocker"

    # Financial API Configuration
    FINNHUB_API_KEY: str = ""
    ALPHA_VANTAGE_API_KEY: str = ""
    ACTIVE_PROVIDER: str = "finnhub" # Default provider

    model_config = ConfigDict(env_file=".env")

    @model_validator(mode="before")
    @classmethod
    def apply_legacy_timer_interval(cls, data):
        if not isinstance(data, dict):
            return data
        if "SCHEDULE_FREQUENCY_MINUTES" not in data and "TIMER_INTERVAL" in data:
            data = dict(data)
            data["SCHEDULE_FREQUENCY_MINUTES"] = _frequency_from_timer_interval(
                data["TIMER_INTERVAL"]
            )
        return data

    @field_validator("SCHEDULE_FREQUENCY_MINUTES")
    @classmethod
    def validate_schedule_frequency(cls, value: int) -> int:
        return schedule_rules.normalize_frequency(value)

    @field_validator("SCHEDULE_START_TIME", "SCHEDULE_END_TIME")
    @classmethod
    def validate_schedule_time(cls, value: str) -> str:
        return schedule_rules.normalize_schedule_time(value)

    @field_validator("SCHEDULE_TIMEZONE")
    @classmethod
    def validate_schedule_timezone(cls, value: str) -> str:
        return schedule_rules.normalize_timezone(value)

    @model_validator(mode="after")
    def validate_schedule_window(self):
        schedule_rules.validate_schedule_window(
            self.SCHEDULE_START_TIME,
            self.SCHEDULE_END_TIME,
        )
        self.TIMER_INTERVAL = self.SCHEDULE_FREQUENCY_MINUTES * 60
        return self

settings = Settings()

# Redis client instance
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

def _safe_setting(setting_name: str, raw_value, fallback, normalizer):
    if raw_value is None:
        return fallback

    try:
        return normalizer(raw_value)
    except schedule_rules.ScheduleValidationError as exc:
        logger.warning(
            "Invalid persisted %s=%r; using fallback %r. Error: %s",
            setting_name,
            raw_value,
            fallback,
            exc,
        )
        return fallback


async def get_dynamic_settings() -> dict:
    """Retrieves dynamic settings from Redis."""
    symbol = await redis_client.get("stocker:settings:symbol") or settings.SYMBOL
    raw_frequency = await redis_client.get("stocker:settings:schedule_frequency_minutes")
    frequency = _safe_setting(
        "schedule_frequency_minutes",
        raw_frequency,
        settings.SCHEDULE_FREQUENCY_MINUTES,
        schedule_rules.normalize_frequency,
    )
    if raw_frequency is None:
        raw_legacy_frequency = await redis_client.get(
            "stocker:settings:timer_interval"
        )
        frequency = _safe_setting(
            "timer_interval",
            raw_legacy_frequency,
            frequency,
            _frequency_from_timer_interval,
        )
        if raw_legacy_frequency is not None:
            try:
                migrated_frequency = _frequency_from_timer_interval(
                    raw_legacy_frequency
                )
            except schedule_rules.ScheduleValidationError:
                pass
            else:
                migrated = await redis_client.set(
                    "stocker:settings:schedule_frequency_minutes",
                    migrated_frequency,
                    nx=True,
                )
                if migrated:
                    frequency = migrated_frequency
                else:
                    concurrent_frequency = await redis_client.get(
                        "stocker:settings:schedule_frequency_minutes"
                    )
                    frequency = _safe_setting(
                        "schedule_frequency_minutes",
                        concurrent_frequency,
                        settings.SCHEDULE_FREQUENCY_MINUTES,
                        schedule_rules.normalize_frequency,
                    )

    raw_start_time = await redis_client.get(
        "stocker:settings:schedule_start_time"
    )
    raw_end_time = await redis_client.get("stocker:settings:schedule_end_time")
    candidate_start_time = (
        raw_start_time
        if raw_start_time is not None
        else settings.SCHEDULE_START_TIME
    )
    candidate_end_time = (
        raw_end_time if raw_end_time is not None else settings.SCHEDULE_END_TIME
    )
    try:
        start_time, end_time = schedule_rules.validate_schedule_window(
            candidate_start_time,
            candidate_end_time,
        )
    except schedule_rules.ScheduleValidationError as exc:
        logger.warning(
            "Invalid persisted schedule window %r-%r; using fallback %s-%s. Error: %s",
            raw_start_time,
            raw_end_time,
            settings.SCHEDULE_START_TIME,
            settings.SCHEDULE_END_TIME,
            exc,
        )
        start_time = settings.SCHEDULE_START_TIME
        end_time = settings.SCHEDULE_END_TIME

    timezone = _safe_setting(
        "schedule_timezone",
        await redis_client.get("stocker:settings:schedule_timezone"),
        settings.SCHEDULE_TIMEZONE,
        schedule_rules.normalize_timezone,
    )

    return {
        "SYMBOL": symbol,
        "SCHEDULE_FREQUENCY_MINUTES": frequency,
        "TIMER_INTERVAL": frequency * 60,
        "SCHEDULE_START_TIME": start_time,
        "SCHEDULE_END_TIME": end_time,
        "SCHEDULE_TIMEZONE": timezone,
    }


async def load_settings_from_redis():
    """Loads dynamic settings from Redis into the global settings object."""
    dynamic_settings = await get_dynamic_settings()
    settings.SYMBOL = dynamic_settings["SYMBOL"]
    settings.SCHEDULE_FREQUENCY_MINUTES = dynamic_settings["SCHEDULE_FREQUENCY_MINUTES"]
    settings.TIMER_INTERVAL = dynamic_settings["TIMER_INTERVAL"]
    settings.SCHEDULE_START_TIME = dynamic_settings["SCHEDULE_START_TIME"]
    settings.SCHEDULE_END_TIME = dynamic_settings["SCHEDULE_END_TIME"]
    settings.SCHEDULE_TIMEZONE = dynamic_settings["SCHEDULE_TIMEZONE"]
