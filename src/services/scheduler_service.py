import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Awaitable, Callable
from uuid import uuid4
from zoneinfo import ZoneInfo

from telegram.ext import ContextTypes, JobQueue

from .. import config
from . import schedule_rules


logger = logging.getLogger(__name__)

PRICE_UPDATE_OPEN_JOB_NAME = "price_update_open"
PRICE_UPDATE_CRON_JOB_NAME = "price_update_cron"
LEGACY_PRICE_UPDATE_JOB_NAME = "price_update"
PRICE_UPDATE_JOB_NAMES = (
    PRICE_UPDATE_OPEN_JOB_NAME,
    PRICE_UPDATE_CRON_JOB_NAME,
    LEGACY_PRICE_UPDATE_JOB_NAME,
)
SCHEDULE_GENERATION_DATA_KEY = "schedule_generation"
SCHEDULE_JOB_KIND_DATA_KEY = "schedule_job_kind"

SCHEDULE_STATE_ACTIVE = "active"
SCHEDULE_STATE_DEGRADED = "degraded"
SCHEDULE_CLAIM_TTL_SECONDS = 172800
_schedule_state = SCHEDULE_STATE_ACTIVE
_active_schedule: "ScheduleConfig | None" = None
_active_schedule_generation: str | None = None

JobCallback = Callable[[ContextTypes.DEFAULT_TYPE], Awaitable[None]]


@dataclass(frozen=True)
class ScheduleConfig:
    frequency_minutes: int
    start_time: str
    end_time: str
    timezone_name: str

    def __post_init__(self) -> None:
        frequency = schedule_rules.normalize_frequency(self.frequency_minutes)
        start_time, end_time = schedule_rules.validate_schedule_window(
            self.start_time,
            self.end_time,
        )
        timezone_name = schedule_rules.normalize_timezone(self.timezone_name)
        object.__setattr__(self, "frequency_minutes", frequency)
        object.__setattr__(self, "start_time", start_time)
        object.__setattr__(self, "end_time", end_time)
        object.__setattr__(self, "timezone_name", timezone_name)


@dataclass(frozen=True)
class _JobSpec:
    name: str
    trigger: schedule_rules.DSTSafeCronTrigger


class JobRemovalError(RuntimeError):
    """Raised when one or more owned jobs cannot be removed."""

    def __init__(self, errors: list[Exception]):
        self.errors = tuple(errors)
        super().__init__(
            "; ".join(str(error) for error in errors)
            or "Unknown job removal failure"
        )


class ScheduleRegistrationError(RuntimeError):
    """Raised when a candidate schedule cannot be registered."""

    def __init__(self, primary_error: Exception):
        self.primary_error = primary_error
        super().__init__(f"Failed to register schedule: {primary_error}")


class ScheduleRollbackError(ScheduleRegistrationError):
    """Raised when schedule replacement and restoration both fail."""

    def __init__(self, primary_error: Exception, rollback_error: Exception):
        self.rollback_error = rollback_error
        super().__init__(primary_error)
        self.args = (
            f"Failed to replace schedule ({primary_error}) and restore previous "
            f"schedule ({rollback_error})",
        )


def schedule_state() -> str:
    return _schedule_state


def _set_schedule_state(value: str) -> None:
    global _schedule_state
    _schedule_state = value


def mark_schedule_active() -> None:
    _set_schedule_state(SCHEDULE_STATE_ACTIVE)


def mark_schedule_degraded() -> None:
    _set_schedule_state(SCHEDULE_STATE_DEGRADED)


def _publish_active_schedule(schedule: ScheduleConfig, generation: str) -> None:
    global _active_schedule, _active_schedule_generation
    _active_schedule = schedule
    _active_schedule_generation = generation
    mark_schedule_active()


def _invalidate_active_generation() -> None:
    global _active_schedule_generation
    _active_schedule_generation = None


def _clear_active_schedule() -> None:
    global _active_schedule, _active_schedule_generation
    _active_schedule = None
    _active_schedule_generation = None


def _reset_schedule_runtime_state() -> None:
    """Reset module runtime state; used to isolate process-lifecycle tests."""
    _clear_active_schedule()
    mark_schedule_active()


def active_schedule_config() -> ScheduleConfig | None:
    return _active_schedule


def current_schedule_config() -> ScheduleConfig:
    return ScheduleConfig(
        frequency_minutes=config.settings.SCHEDULE_FREQUENCY_MINUTES,
        start_time=config.settings.SCHEDULE_START_TIME,
        end_time=config.settings.SCHEDULE_END_TIME,
        timezone_name=config.settings.SCHEDULE_TIMEZONE,
    )


def _build_job_specs(schedule: ScheduleConfig) -> tuple[_JobSpec, ...]:
    specs: list[_JobSpec] = []
    if not schedule_rules.is_recurring_boundary(
        schedule.start_time,
        schedule.frequency_minutes,
    ):
        specs.append(
            _JobSpec(
                name=PRICE_UPDATE_OPEN_JOB_NAME,
                trigger=schedule_rules.build_opening_trigger(
                    schedule.start_time,
                    schedule.timezone_name,
                ),
            )
        )

    specs.append(
        _JobSpec(
            name=PRICE_UPDATE_CRON_JOB_NAME,
            trigger=schedule_rules.build_price_update_trigger(
                schedule.frequency_minutes,
                schedule.timezone_name,
            ),
        )
    )
    return tuple(specs)


def remove_price_update_jobs(job_queue: JobQueue) -> None:
    errors: list[Exception] = []
    for job_name in PRICE_UPDATE_JOB_NAMES:
        try:
            jobs = job_queue.get_jobs_by_name(job_name)
        except Exception as error:
            errors.append(error)
            continue

        for job in jobs:
            try:
                job.schedule_removal()
            except Exception as error:
                errors.append(error)

    if errors:
        raise JobRemovalError(errors)


def _register_job_specs(
    job_queue: JobQueue,
    callback: JobCallback,
    specs: tuple[_JobSpec, ...],
    generation: str,
) -> list:
    registered_jobs: list = []
    for spec in specs:
        registered_jobs.append(
            job_queue.run_custom(
                callback,
                job_kwargs={
                    "trigger": spec.trigger,
                    "coalesce": True,
                    "max_instances": 1,
                    "misfire_grace_time": 1,
                },
                data={
                    SCHEDULE_GENERATION_DATA_KEY: generation,
                    SCHEDULE_JOB_KIND_DATA_KEY: spec.name,
                },
                name=spec.name,
            )
        )
    return registered_jobs


def _fail_degraded(
    primary_error: Exception,
    rollback_error: Exception | None = None,
):
    _clear_active_schedule()
    mark_schedule_degraded()
    if rollback_error is not None:
        raise ScheduleRollbackError(primary_error, rollback_error) from rollback_error
    raise ScheduleRegistrationError(primary_error) from primary_error


def _restore_previous_schedule(
    job_queue: JobQueue,
    callback: JobCallback,
    rollback_schedule: ScheduleConfig | None,
    rollback_specs: tuple[_JobSpec, ...] | None,
    primary_error: Exception,
):
    try:
        remove_price_update_jobs(job_queue)
    except Exception as cleanup_error:
        _fail_degraded(primary_error, cleanup_error)

    if rollback_schedule is None or rollback_specs is None:
        _fail_degraded(primary_error)

    rollback_generation = uuid4().hex
    try:
        _register_job_specs(
            job_queue,
            callback,
            rollback_specs,
            rollback_generation,
        )
    except Exception as rollback_error:
        try:
            remove_price_update_jobs(job_queue)
        except Exception:
            logger.exception("Failed to clean up partially restored schedule jobs.")
        _fail_degraded(primary_error, rollback_error)

    _publish_active_schedule(rollback_schedule, rollback_generation)
    raise ScheduleRegistrationError(primary_error) from primary_error


def schedule_price_update(
    job_queue: JobQueue | None,
    callback: JobCallback,
    *,
    schedule: ScheduleConfig | None = None,
    rollback_schedule: ScheduleConfig | None = None,
):
    if job_queue is None:
        error = RuntimeError("Job queue is not available.")
        mark_schedule_degraded()
        logger.error("Price update jobs were not scheduled: %s", error)
        raise ScheduleRegistrationError(error)

    candidate = schedule or current_schedule_config()
    effective_rollback = rollback_schedule or _active_schedule
    candidate_specs = _build_job_specs(candidate)
    rollback_specs = (
        _build_job_specs(effective_rollback)
        if effective_rollback is not None
        else None
    )
    candidate_generation = uuid4().hex

    _invalidate_active_generation()
    try:
        remove_price_update_jobs(job_queue)
    except Exception as primary_error:
        _restore_previous_schedule(
            job_queue,
            callback,
            effective_rollback,
            rollback_specs,
            primary_error,
        )

    try:
        candidate_jobs = _register_job_specs(
            job_queue,
            callback,
            candidate_specs,
            candidate_generation,
        )
    except Exception as primary_error:
        _restore_previous_schedule(
            job_queue,
            callback,
            effective_rollback,
            rollback_specs,
            primary_error,
        )

    _publish_active_schedule(candidate, candidate_generation)
    return candidate_jobs


def reschedule_price_update(
    job_queue: JobQueue | None,
    callback: JobCallback,
    *,
    schedule: ScheduleConfig | None = None,
    rollback_schedule: ScheduleConfig | None = None,
):
    effective_rollback = rollback_schedule or _active_schedule
    if effective_rollback is None:
        error = RuntimeError(
            "Cannot reschedule without a known active schedule. "
            "Use schedule_price_update() for initial registration."
        )
        raise ScheduleRegistrationError(error)

    return schedule_price_update(
        job_queue,
        callback,
        schedule=schedule,
        rollback_schedule=effective_rollback,
    )


def schedule_for_callback(job, now: datetime) -> ScheduleConfig | None:
    """Return the active schedule only for a current, valid owned-job callback."""
    schedule = _active_schedule
    generation = _active_schedule_generation
    if schedule is None or generation is None or job is None:
        return None

    data = getattr(job, "data", None)
    if not isinstance(data, dict):
        return None
    if data.get(SCHEDULE_GENERATION_DATA_KEY) != generation:
        return None

    job_kind = data.get(SCHEDULE_JOB_KIND_DATA_KEY)
    if job_kind != getattr(job, "name", None):
        return None

    timezone = ZoneInfo(schedule.timezone_name)
    local_now = now.astimezone(timezone)
    if local_now.fold != 0:
        return None
    local_time = local_now.strftime("%H:%M")

    if job_kind == PRICE_UPDATE_CRON_JOB_NAME:
        if not schedule_rules.is_recurring_boundary(
            local_time,
            schedule.frequency_minutes,
        ):
            return None
    elif job_kind == PRICE_UPDATE_OPEN_JOB_NAME:
        if local_time != schedule.start_time or schedule_rules.is_recurring_boundary(
            schedule.start_time,
            schedule.frequency_minutes,
        ):
            return None
    else:
        return None

    return schedule


def current_schedule_datetime(schedule: ScheduleConfig | None = None) -> datetime:
    effective = schedule or current_schedule_config()
    return datetime.now(ZoneInfo(effective.timezone_name))


async def claim_scheduled_update(
    now: datetime | None = None,
    schedule: ScheduleConfig | None = None,
) -> bool:
    """Atomically claim one timezone-local scheduled update occurrence."""
    effective = schedule or current_schedule_config()
    timezone = ZoneInfo(effective.timezone_name)
    current = now.astimezone(timezone) if now else current_schedule_datetime(effective)
    if current.fold != 0:
        logger.info(
            "Skipping repeated fall-back scheduled occurrence: %s %s",
            effective.timezone_name,
            current.strftime("%Y-%m-%d %H:%M"),
        )
        return False

    claim_key = (
        f"stocker:schedule:sent:{effective.timezone_name}:"
        f"{current.strftime('%Y-%m-%d:%H:%M')}"
    )
    try:
        claimed = await config.redis_client.set(
            claim_key,
            "1",
            nx=True,
            ex=SCHEDULE_CLAIM_TTL_SECONDS,
        )
    except Exception:
        mark_schedule_degraded()
        logger.exception(
            "Failed to claim scheduled price update occurrence; failing closed: %s",
            claim_key,
        )
        return False

    return bool(claimed)


def should_run_scheduled_update(
    now: datetime | None = None,
    schedule: ScheduleConfig | None = None,
) -> bool:
    effective = schedule or current_schedule_config()
    timezone = ZoneInfo(effective.timezone_name)
    current = now.astimezone(timezone) if now else current_schedule_datetime(effective)
    return schedule_rules.is_datetime_within_window(
        current,
        effective.start_time,
        effective.end_time,
        effective.timezone_name,
    )


def schedule_summary(schedule: ScheduleConfig | None = None) -> str:
    effective = schedule or current_schedule_config()
    return (
        f"{effective.frequency_minutes} minute(s), "
        f"{effective.start_time}-{effective.end_time} "
        f"{effective.timezone_name}"
    )
