import asyncio

from .. import config
from . import schedule_rules, scheduler_service


SCHEDULE_FREQUENCY_KEY = "stocker:settings:schedule_frequency_minutes"
LEGACY_TIMER_INTERVAL_KEY = "stocker:settings:timer_interval"
SCHEDULE_START_TIME_KEY = "stocker:settings:schedule_start_time"
SCHEDULE_END_TIME_KEY = "stocker:settings:schedule_end_time"
SCHEDULE_TIMEZONE_KEY = "stocker:settings:schedule_timezone"
SCHEDULE_REDIS_KEYS = (
    SCHEDULE_FREQUENCY_KEY,
    LEGACY_TIMER_INTERVAL_KEY,
    SCHEDULE_START_TIME_KEY,
    SCHEDULE_END_TIME_KEY,
    SCHEDULE_TIMEZONE_KEY,
)

_schedule_update_lock = asyncio.Lock()


class ScheduleUpdateError(RuntimeError):
    """Raised after a schedule update fails and prior state is restored."""

    def __init__(self, primary_error: Exception):
        self.primary_error = primary_error
        super().__init__(f"Schedule update failed: {primary_error}")


class ScheduleUpdateRollbackError(ScheduleUpdateError):
    """Raised when a schedule update and its compensating rollback both fail."""

    def __init__(self, primary_error: Exception, rollback_error: Exception):
        self.rollback_error = rollback_error
        super().__init__(primary_error)
        self.args = (
            f"Schedule update failed ({primary_error}) and rollback was incomplete "
            f"({rollback_error})",
        )


async def update_symbol(new_symbol: str):
    """Updates the symbol in Redis."""
    await config.redis_client.set("stocker:settings:symbol", new_symbol)
    config.settings.SYMBOL = new_symbol


def _persisted_values(
    schedule: scheduler_service.ScheduleConfig,
) -> dict[str, str | int]:
    return {
        SCHEDULE_FREQUENCY_KEY: schedule.frequency_minutes,
        LEGACY_TIMER_INTERVAL_KEY: schedule.frequency_minutes * 60,
        SCHEDULE_START_TIME_KEY: schedule.start_time,
        SCHEDULE_END_TIME_KEY: schedule.end_time,
        SCHEDULE_TIMEZONE_KEY: schedule.timezone_name,
    }


async def _snapshot_raw_persisted_values() -> dict[str, str | None]:
    values = await config.redis_client.mget(*SCHEDULE_REDIS_KEYS)
    return dict(zip(SCHEDULE_REDIS_KEYS, values, strict=True))


async def _write_persisted_values(values: dict[str, str | int | None]) -> None:
    async with config.redis_client.pipeline(transaction=True) as pipeline:
        for key in SCHEDULE_REDIS_KEYS:
            value = values.get(key)
            if value is None:
                pipeline.delete(key)
            else:
                pipeline.set(key, value)
        await pipeline.execute()


def _activate_schedule(schedule: scheduler_service.ScheduleConfig) -> None:
    config.settings.SCHEDULE_FREQUENCY_MINUTES = schedule.frequency_minutes
    config.settings.TIMER_INTERVAL = schedule.frequency_minutes * 60
    config.settings.SCHEDULE_START_TIME = schedule.start_time
    config.settings.SCHEDULE_END_TIME = schedule.end_time
    config.settings.SCHEDULE_TIMEZONE = schedule.timezone_name


async def apply_schedule_change(
    *,
    job_queue,
    callback,
    frequency_minutes: int | str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    timezone_name: str | None = None,
) -> scheduler_service.ScheduleConfig:
    """Validate, persist, activate, and reschedule one atomic schedule change."""
    async with _schedule_update_lock:
        previous = scheduler_service.current_schedule_config()
        candidate = scheduler_service.ScheduleConfig(
            frequency_minutes=(
                previous.frequency_minutes
                if frequency_minutes is None
                else frequency_minutes
            ),
            start_time=previous.start_time if start_time is None else start_time,
            end_time=previous.end_time if end_time is None else end_time,
            timezone_name=(
                previous.timezone_name if timezone_name is None else timezone_name
            ),
        )

        try:
            previous_raw = await _snapshot_raw_persisted_values()
        except Exception as primary_error:
            raise ScheduleUpdateError(primary_error) from primary_error

        try:
            await _write_persisted_values(_persisted_values(candidate))
        except Exception as primary_error:
            try:
                await _write_persisted_values(previous_raw)
            except Exception as rollback_error:
                scheduler_service.mark_schedule_degraded()
                raise ScheduleUpdateRollbackError(
                    primary_error,
                    rollback_error,
                ) from rollback_error
            raise ScheduleUpdateError(primary_error) from primary_error

        _activate_schedule(candidate)
        try:
            scheduler_service.reschedule_price_update(
                job_queue,
                callback,
                schedule=candidate,
                rollback_schedule=previous,
            )
        except Exception as primary_error:
            _activate_schedule(previous)
            try:
                await _write_persisted_values(previous_raw)
            except Exception as rollback_error:
                scheduler_service.mark_schedule_degraded()
                raise ScheduleUpdateRollbackError(
                    primary_error,
                    rollback_error,
                ) from rollback_error

            if isinstance(primary_error, scheduler_service.ScheduleRollbackError):
                scheduler_service.mark_schedule_degraded()
                raise ScheduleUpdateRollbackError(
                    primary_error.primary_error,
                    primary_error.rollback_error,
                ) from primary_error
            raise ScheduleUpdateError(primary_error) from primary_error

        scheduler_service.mark_schedule_active()
        return candidate


async def update_schedule_frequency_minutes(
    new_frequency: int | str,
    *,
    job_queue,
    callback,
):
    return await apply_schedule_change(
        job_queue=job_queue,
        callback=callback,
        frequency_minutes=new_frequency,
    )


async def update_timer_interval(
    new_interval: int,
    *,
    job_queue,
    callback,
):
    if new_interval % 60 != 0:
        raise schedule_rules.ScheduleValidationError(
            "Timer interval must be a whole number of minutes."
        )
    return await update_schedule_frequency_minutes(
        new_interval // 60,
        job_queue=job_queue,
        callback=callback,
    )


async def update_schedule_window(
    start_time: str,
    end_time: str,
    *,
    job_queue,
    callback,
):
    return await apply_schedule_change(
        job_queue=job_queue,
        callback=callback,
        start_time=start_time,
        end_time=end_time,
    )


async def update_schedule_timezone(
    timezone: str,
    *,
    job_queue,
    callback,
):
    return await apply_schedule_change(
        job_queue=job_queue,
        callback=callback,
        timezone_name=timezone,
    )
