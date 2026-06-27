from .. import config
from . import schedule_rules

async def update_symbol(new_symbol: str):
    """Updates the symbol in Redis."""
    await config.redis_client.set("stocker:settings:symbol", new_symbol)
    config.settings.SYMBOL = new_symbol # Update in-memory settings as well

async def update_schedule_frequency_minutes(new_frequency: int):
    """Updates the schedule frequency in Redis."""
    frequency = schedule_rules.normalize_frequency(new_frequency)
    await config.redis_client.set("stocker:settings:schedule_frequency_minutes", frequency)
    await config.redis_client.set("stocker:settings:timer_interval", frequency * 60)
    config.settings.SCHEDULE_FREQUENCY_MINUTES = frequency
    config.settings.TIMER_INTERVAL = frequency * 60

async def update_timer_interval(new_interval: int):
    """Updates the timer interval in Redis."""
    if new_interval % 60 != 0:
        raise schedule_rules.ScheduleValidationError(
            "Timer interval must be a whole number of minutes."
        )
    await update_schedule_frequency_minutes(new_interval // 60)

async def update_schedule_window(start_time: str, end_time: str):
    """Updates the active schedule window in Redis."""
    normalized_start, normalized_end = schedule_rules.validate_schedule_window(
        start_time,
        end_time,
    )
    await config.redis_client.set("stocker:settings:schedule_start_time", normalized_start)
    await config.redis_client.set("stocker:settings:schedule_end_time", normalized_end)
    config.settings.SCHEDULE_START_TIME = normalized_start
    config.settings.SCHEDULE_END_TIME = normalized_end

async def update_schedule_timezone(timezone: str):
    """Updates the schedule timezone in Redis."""
    normalized_timezone = schedule_rules.normalize_timezone(timezone)
    await config.redis_client.set("stocker:settings:schedule_timezone", normalized_timezone)
    config.settings.SCHEDULE_TIMEZONE = normalized_timezone
