import logging
from datetime import datetime
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

from telegram.ext import ContextTypes, JobQueue

from .. import config
from . import schedule_rules


logger = logging.getLogger(__name__)

PRICE_UPDATE_JOB_NAME = "price_update"

JobCallback = Callable[[ContextTypes.DEFAULT_TYPE], Awaitable[None]]


def remove_price_update_jobs(job_queue: JobQueue) -> None:
    for job in job_queue.get_jobs_by_name(PRICE_UPDATE_JOB_NAME):
        job.schedule_removal()


def schedule_price_update(job_queue: JobQueue | None, callback: JobCallback):
    if not job_queue:
        logger.warning("Job queue is not available; price update job was not scheduled.")
        return None

    remove_price_update_jobs(job_queue)
    trigger = schedule_rules.build_price_update_trigger(
        config.settings.SCHEDULE_FREQUENCY_MINUTES,
        config.settings.SCHEDULE_TIMEZONE,
    )
    return job_queue.run_custom(
        callback,
        job_kwargs={"trigger": trigger},
        name=PRICE_UPDATE_JOB_NAME,
    )


def reschedule_price_update(job_queue: JobQueue | None, callback: JobCallback):
    return schedule_price_update(job_queue, callback)


def should_run_scheduled_update(now: datetime | None = None) -> bool:
    timezone = ZoneInfo(config.settings.SCHEDULE_TIMEZONE)
    current = now.astimezone(timezone) if now else datetime.now(timezone)
    return schedule_rules.is_datetime_within_window(
        current,
        config.settings.SCHEDULE_START_TIME,
        config.settings.SCHEDULE_END_TIME,
        config.settings.SCHEDULE_TIMEZONE,
    )


def schedule_summary() -> str:
    return (
        f"{config.settings.SCHEDULE_FREQUENCY_MINUTES} minute(s), "
        f"{config.settings.SCHEDULE_START_TIME}-{config.settings.SCHEDULE_END_TIME} "
        f"{config.settings.SCHEDULE_TIMEZONE}"
    )
