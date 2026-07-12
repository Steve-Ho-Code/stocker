import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src import config
from src.services import schedule_rules, scheduler_service


class FakeJob:
    def __init__(
        self,
        name=None,
        callback=None,
        job_kwargs=None,
        data=None,
        removal_failures=0,
    ):
        self.name = name
        self.callback = callback
        self.job_kwargs = job_kwargs or {}
        self.data = data
        self.removal_failures = removal_failures
        self.removal_attempts = 0
        self.removed = False

    def schedule_removal(self):
        self.removal_attempts += 1
        if self.removal_failures:
            self.removal_failures -= 1
            raise RuntimeError("removal failure")
        self.removed = True


class FakeJobQueue:
    def __init__(self, jobs_by_name=None, fail_on_attempts=None):
        self.jobs_by_name = jobs_by_name or {}
        self.fail_on_attempts = set(fail_on_attempts or [])
        self.run_custom_attempts = []
        self.created_jobs = []

    def get_jobs_by_name(self, name):
        return [job for job in self.jobs_by_name.get(name, []) if not job.removed]

    def run_custom(self, callback, job_kwargs, data=None, name=None):
        attempt = len(self.run_custom_attempts) + 1
        self.run_custom_attempts.append(
            {
                "callback": callback,
                "job_kwargs": job_kwargs,
                "data": data,
                "name": name,
            }
        )
        if attempt in self.fail_on_attempts:
            raise RuntimeError(f"registration failure {attempt}")

        job = FakeJob(
            name=name,
            callback=callback,
            job_kwargs=job_kwargs,
            data=data,
        )
        self.created_jobs.append(job)
        self.jobs_by_name.setdefault(name, []).append(job)
        return job


async def fake_callback(context):
    return None


class FakeClaimRedis:
    def __init__(self, error=None):
        self.error = error
        self.keys = set()
        self.calls = []

    async def set(self, key, value, **kwargs):
        self.calls.append((key, value, kwargs))
        if self.error is not None:
            raise self.error
        if kwargs.get("nx") and key in self.keys:
            return None
        self.keys.add(key)
        return True


def patch_schedule(mocker, frequency, start_time, end_time="16:00", timezone="UTC"):
    mocker.patch.object(config.settings, "SCHEDULE_FREQUENCY_MINUTES", frequency)
    mocker.patch.object(config.settings, "SCHEDULE_START_TIME", start_time)
    mocker.patch.object(config.settings, "SCHEDULE_END_TIME", end_time)
    mocker.patch.object(config.settings, "SCHEDULE_TIMEZONE", timezone)


def test_schedule_price_update_registers_open_and_cron_for_off_boundary_start(mocker):
    patch_schedule(mocker, frequency=15, start_time="09:33")
    existing_jobs = {
        scheduler_service.PRICE_UPDATE_OPEN_JOB_NAME: [FakeJob()],
        scheduler_service.PRICE_UPDATE_CRON_JOB_NAME: [FakeJob()],
        scheduler_service.LEGACY_PRICE_UPDATE_JOB_NAME: [FakeJob()],
    }
    original_jobs = [job for jobs in existing_jobs.values() for job in jobs]
    job_queue = FakeJobQueue(jobs_by_name=existing_jobs)

    scheduler_service.schedule_price_update(job_queue, fake_callback)

    assert all(job.removed for job in original_jobs)
    assert [call["name"] for call in job_queue.run_custom_attempts] == [
        scheduler_service.PRICE_UPDATE_OPEN_JOB_NAME,
        scheduler_service.PRICE_UPDATE_CRON_JOB_NAME,
    ]
    for call in job_queue.run_custom_attempts:
        assert call["job_kwargs"]["coalesce"] is True
        assert call["job_kwargs"]["max_instances"] == 1
        assert call["job_kwargs"]["misfire_grace_time"] == 1


def test_schedule_price_update_omits_open_job_for_on_boundary_start(mocker):
    patch_schedule(mocker, frequency=15, start_time="09:30")
    job_queue = FakeJobQueue()

    scheduler_service.schedule_price_update(job_queue, fake_callback)

    assert [call["name"] for call in job_queue.run_custom_attempts] == [
        scheduler_service.PRICE_UPDATE_CRON_JOB_NAME
    ]


def test_repeated_reschedule_leaves_one_complete_active_job_set(mocker):
    patch_schedule(mocker, frequency=15, start_time="09:33")
    job_queue = FakeJobQueue()

    scheduler_service.schedule_price_update(job_queue, fake_callback)
    scheduler_service.reschedule_price_update(job_queue, fake_callback)

    assert len(job_queue.get_jobs_by_name(
        scheduler_service.PRICE_UPDATE_OPEN_JOB_NAME
    )) == 1
    assert len(job_queue.get_jobs_by_name(
        scheduler_service.PRICE_UPDATE_CRON_JOB_NAME
    )) == 1
    assert job_queue.get_jobs_by_name(
        scheduler_service.LEGACY_PRICE_UPDATE_JOB_NAME
    ) == []


def test_reschedule_after_boundary_second_selects_next_recurring_boundary(mocker):
    patch_schedule(mocker, frequency=15, start_time="09:30")
    job_queue = FakeJobQueue()

    scheduler_service.schedule_price_update(job_queue, fake_callback)

    trigger = job_queue.created_jobs[0].job_kwargs["trigger"]
    assert trigger.get_next_fire_time(
        None,
        datetime(2026, 1, 1, 9, 30, 1, tzinfo=ZoneInfo("UTC")),
    ) == datetime(2026, 1, 1, 9, 45, tzinfo=ZoneInfo("UTC"))


def test_trigger_validation_failure_leaves_existing_jobs_untouched(mocker):
    patch_schedule(mocker, frequency=7, start_time="09:30")
    existing_job = FakeJob()
    job_queue = FakeJobQueue(
        jobs_by_name={scheduler_service.LEGACY_PRICE_UPDATE_JOB_NAME: [existing_job]}
    )

    with pytest.raises(schedule_rules.ScheduleValidationError):
        scheduler_service.schedule_price_update(job_queue, fake_callback)

    assert existing_job.removed is False
    assert job_queue.run_custom_attempts == []


def test_removal_failure_restores_complete_previous_schedule():
    previous = scheduler_service.ScheduleConfig(15, "09:33", "16:00", "UTC")
    candidate = scheduler_service.ScheduleConfig(60, "09:30", "16:00", "UTC")
    existing_open = FakeJob(name=scheduler_service.PRICE_UPDATE_OPEN_JOB_NAME)
    existing_cron = FakeJob(
        name=scheduler_service.PRICE_UPDATE_CRON_JOB_NAME,
        removal_failures=1,
    )
    job_queue = FakeJobQueue(
        jobs_by_name={
            scheduler_service.PRICE_UPDATE_OPEN_JOB_NAME: [existing_open],
            scheduler_service.PRICE_UPDATE_CRON_JOB_NAME: [existing_cron],
        }
    )

    with pytest.raises(scheduler_service.ScheduleRegistrationError):
        scheduler_service.schedule_price_update(
            job_queue,
            fake_callback,
            schedule=candidate,
            rollback_schedule=previous,
        )

    assert existing_open.removed is True
    assert existing_cron.removed is True
    assert len(
        job_queue.get_jobs_by_name(scheduler_service.PRICE_UPDATE_OPEN_JOB_NAME)
    ) == 1
    assert len(
        job_queue.get_jobs_by_name(scheduler_service.PRICE_UPDATE_CRON_JOB_NAME)
    ) == 1
    assert scheduler_service.schedule_state() == scheduler_service.SCHEDULE_STATE_ACTIVE


def test_persistent_removal_failure_marks_scheduler_degraded():
    previous = scheduler_service.ScheduleConfig(15, "09:33", "16:00", "UTC")
    candidate = scheduler_service.ScheduleConfig(60, "09:30", "16:00", "UTC")
    failing_job = FakeJob(
        name=scheduler_service.PRICE_UPDATE_CRON_JOB_NAME,
        removal_failures=10,
    )
    job_queue = FakeJobQueue(
        jobs_by_name={scheduler_service.PRICE_UPDATE_CRON_JOB_NAME: [failing_job]}
    )

    with pytest.raises(scheduler_service.ScheduleRollbackError):
        scheduler_service.schedule_price_update(
            job_queue,
            fake_callback,
            schedule=candidate,
            rollback_schedule=previous,
        )

    assert scheduler_service.schedule_state() == scheduler_service.SCHEDULE_STATE_DEGRADED


def test_missing_job_queue_is_a_registration_failure(mocker):
    patch_schedule(mocker, frequency=15, start_time="09:30")

    with pytest.raises(scheduler_service.ScheduleRegistrationError):
        scheduler_service.schedule_price_update(None, fake_callback)

    assert scheduler_service.schedule_state() == scheduler_service.SCHEDULE_STATE_DEGRADED


def test_partial_registration_failure_restores_previous_schedule():
    previous = scheduler_service.ScheduleConfig(
        frequency_minutes=15,
        start_time="09:30",
        end_time="16:00",
        timezone_name="UTC",
    )
    candidate = scheduler_service.ScheduleConfig(
        frequency_minutes=15,
        start_time="09:33",
        end_time="16:00",
        timezone_name="UTC",
    )
    job_queue = FakeJobQueue(fail_on_attempts={2})

    with pytest.raises(scheduler_service.ScheduleRegistrationError):
        scheduler_service.schedule_price_update(
            job_queue,
            fake_callback,
            schedule=candidate,
            rollback_schedule=previous,
        )

    assert job_queue.created_jobs[0].removed is True
    assert [call["name"] for call in job_queue.run_custom_attempts] == [
        scheduler_service.PRICE_UPDATE_OPEN_JOB_NAME,
        scheduler_service.PRICE_UPDATE_CRON_JOB_NAME,
        scheduler_service.PRICE_UPDATE_CRON_JOB_NAME,
    ]
    assert job_queue.created_jobs[-1].name == scheduler_service.PRICE_UPDATE_CRON_JOB_NAME
    restored_trigger = job_queue.created_jobs[-1].job_kwargs["trigger"]
    assert restored_trigger.get_next_fire_time(
        None, datetime(2026, 1, 1, 9, 29, tzinfo=ZoneInfo("UTC"))
    ) == datetime(2026, 1, 1, 9, 30, tzinfo=ZoneInfo("UTC"))


def test_partial_failure_restores_complete_off_boundary_job_set():
    previous = scheduler_service.ScheduleConfig(15, "09:33", "16:00", "UTC")
    candidate = scheduler_service.ScheduleConfig(5, "09:07", "16:00", "UTC")
    job_queue = FakeJobQueue(fail_on_attempts={2})

    with pytest.raises(scheduler_service.ScheduleRegistrationError):
        scheduler_service.schedule_price_update(
            job_queue,
            fake_callback,
            schedule=candidate,
            rollback_schedule=previous,
        )

    assert len(
        job_queue.get_jobs_by_name(scheduler_service.PRICE_UPDATE_OPEN_JOB_NAME)
    ) == 1
    assert len(
        job_queue.get_jobs_by_name(scheduler_service.PRICE_UPDATE_CRON_JOB_NAME)
    ) == 1
    assert job_queue.get_jobs_by_name(
        scheduler_service.LEGACY_PRICE_UPDATE_JOB_NAME
    ) == []


def test_partial_rollback_jobs_are_removed_when_restoration_fails():
    previous = scheduler_service.ScheduleConfig(15, "09:33", "16:00", "UTC")
    candidate = scheduler_service.ScheduleConfig(5, "09:07", "16:00", "UTC")
    job_queue = FakeJobQueue(fail_on_attempts={2, 4})

    with pytest.raises(scheduler_service.ScheduleRollbackError):
        scheduler_service.schedule_price_update(
            job_queue,
            fake_callback,
            schedule=candidate,
            rollback_schedule=previous,
        )

    assert job_queue.get_jobs_by_name(
        scheduler_service.PRICE_UPDATE_OPEN_JOB_NAME
    ) == []
    assert job_queue.get_jobs_by_name(
        scheduler_service.PRICE_UPDATE_CRON_JOB_NAME
    ) == []
    assert scheduler_service.schedule_state() == scheduler_service.SCHEDULE_STATE_DEGRADED


def test_direct_reschedule_uses_last_successful_schedule_for_rollback(mocker):
    patch_schedule(mocker, frequency=15, start_time="09:30")
    previous = scheduler_service.ScheduleConfig(15, "09:30", "16:00", "UTC")
    candidate = scheduler_service.ScheduleConfig(60, "09:30", "16:00", "UTC")
    job_queue = FakeJobQueue()
    scheduler_service.schedule_price_update(
        job_queue,
        fake_callback,
        schedule=previous,
    )
    job_queue.fail_on_attempts.add(3)

    with pytest.raises(scheduler_service.ScheduleRegistrationError):
        scheduler_service.reschedule_price_update(
            job_queue,
            fake_callback,
            schedule=candidate,
        )

    active_cron = job_queue.get_jobs_by_name(
        scheduler_service.PRICE_UPDATE_CRON_JOB_NAME
    )
    assert len(active_cron) == 1
    assert job_queue.get_jobs_by_name(
        scheduler_service.PRICE_UPDATE_OPEN_JOB_NAME
    ) == []
    assert active_cron[0].job_kwargs["trigger"].get_next_fire_time(
        None,
        datetime(2026, 1, 1, 9, 31, tzinfo=ZoneInfo("UTC")),
    ) == datetime(2026, 1, 1, 9, 45, tzinfo=ZoneInfo("UTC"))


def test_direct_reschedule_requires_known_previous_schedule_before_removal():
    candidate = scheduler_service.ScheduleConfig(60, "09:30", "16:00", "UTC")
    existing_job = FakeJob(name=scheduler_service.LEGACY_PRICE_UPDATE_JOB_NAME)
    job_queue = FakeJobQueue(
        jobs_by_name={
            scheduler_service.LEGACY_PRICE_UPDATE_JOB_NAME: [existing_job]
        }
    )

    with pytest.raises(scheduler_service.ScheduleRegistrationError):
        scheduler_service.reschedule_price_update(
            job_queue,
            fake_callback,
            schedule=candidate,
        )

    assert existing_job.removed is False
    assert job_queue.run_custom_attempts == []


def test_stale_or_off_boundary_callback_is_rejected(mocker):
    patch_schedule(mocker, frequency=15, start_time="09:30")
    previous = scheduler_service.ScheduleConfig(15, "09:30", "16:00", "UTC")
    candidate = scheduler_service.ScheduleConfig(60, "09:30", "16:00", "UTC")
    job_queue = FakeJobQueue()
    scheduler_service.schedule_price_update(
        job_queue,
        fake_callback,
        schedule=previous,
    )
    stale_job = job_queue.get_jobs_by_name(
        scheduler_service.PRICE_UPDATE_CRON_JOB_NAME
    )[0]
    scheduler_service.reschedule_price_update(
        job_queue,
        fake_callback,
        schedule=candidate,
    )
    active_cron = job_queue.get_jobs_by_name(
        scheduler_service.PRICE_UPDATE_CRON_JOB_NAME
    )[0]

    at_0945 = datetime(2026, 1, 1, 9, 45, tzinfo=ZoneInfo("UTC"))
    at_1000 = datetime(2026, 1, 1, 10, 0, tzinfo=ZoneInfo("UTC"))
    assert scheduler_service.schedule_for_callback(stale_job, at_0945) is None
    assert scheduler_service.schedule_for_callback(active_cron, at_0945) is None
    assert scheduler_service.schedule_for_callback(active_cron, at_1000) == candidate


def test_rollback_registration_failure_marks_scheduler_degraded():
    previous = scheduler_service.ScheduleConfig(15, "09:30", "16:00", "UTC")
    candidate = scheduler_service.ScheduleConfig(15, "09:33", "16:00", "UTC")
    job_queue = FakeJobQueue(fail_on_attempts={2, 3})

    with pytest.raises(scheduler_service.ScheduleRollbackError) as exc_info:
        scheduler_service.schedule_price_update(
            job_queue,
            fake_callback,
            schedule=candidate,
            rollback_schedule=previous,
        )

    assert isinstance(exc_info.value.primary_error, RuntimeError)
    assert isinstance(exc_info.value.rollback_error, RuntimeError)
    assert scheduler_service.schedule_state() == scheduler_service.SCHEDULE_STATE_DEGRADED


@pytest.mark.asyncio
async def test_atomic_claim_allows_only_one_sender_for_same_local_minute(mocker):
    patch_schedule(mocker, frequency=15, start_time="09:30")
    redis = FakeClaimRedis()
    mocker.patch.object(config, "redis_client", redis)
    now = datetime(2026, 1, 1, 10, 0, tzinfo=ZoneInfo("UTC"))

    results = await asyncio.gather(
        scheduler_service.claim_scheduled_update(now),
        scheduler_service.claim_scheduled_update(now),
    )

    assert sorted(results) == [False, True]
    assert redis.calls[0] == (
        "stocker:schedule:sent:UTC:2026-01-01:10:00",
        "1",
        {"nx": True, "ex": scheduler_service.SCHEDULE_CLAIM_TTL_SECONDS},
    )


@pytest.mark.asyncio
async def test_existing_claim_survives_process_recovery(mocker):
    patch_schedule(mocker, frequency=15, start_time="09:30")
    redis = FakeClaimRedis()
    redis.keys.add("stocker:schedule:sent:UTC:2026-01-01:10:00")
    mocker.patch.object(config, "redis_client", redis)
    now = datetime(2026, 1, 1, 10, 0, tzinfo=ZoneInfo("UTC"))

    assert await scheduler_service.claim_scheduled_update(now) is False


@pytest.mark.asyncio
async def test_claim_rejects_second_fall_back_occurrence_without_redis_write(mocker):
    patch_schedule(
        mocker,
        frequency=30,
        start_time="00:00",
        end_time="03:00",
        timezone="America/New_York",
    )
    redis = FakeClaimRedis()
    mocker.patch.object(config, "redis_client", redis)
    now = datetime(
        2026,
        11,
        1,
        1,
        30,
        tzinfo=ZoneInfo("America/New_York"),
        fold=1,
    )

    assert await scheduler_service.claim_scheduled_update(now) is False
    assert redis.calls == []


@pytest.mark.asyncio
async def test_claim_store_failure_fails_closed_and_marks_degraded(mocker):
    patch_schedule(mocker, frequency=15, start_time="09:30")
    mocker.patch.object(config, "redis_client", FakeClaimRedis(RuntimeError("redis down")))
    now = datetime(2026, 1, 1, 10, 0, tzinfo=ZoneInfo("UTC"))

    assert await scheduler_service.claim_scheduled_update(now) is False
    assert scheduler_service.schedule_state() == scheduler_service.SCHEDULE_STATE_DEGRADED


def test_should_run_scheduled_update_inside_window(mocker):
    patch_schedule(
        mocker,
        frequency=15,
        start_time="09:30",
        timezone="America/New_York",
    )
    now = datetime(2026, 1, 1, 10, 0, tzinfo=ZoneInfo("America/New_York"))

    assert scheduler_service.should_run_scheduled_update(now)


def test_should_run_scheduled_update_outside_window(mocker):
    patch_schedule(
        mocker,
        frequency=15,
        start_time="09:30",
        timezone="America/New_York",
    )
    now = datetime(2026, 1, 1, 8, 0, tzinfo=ZoneInfo("America/New_York"))

    assert not scheduler_service.should_run_scheduled_update(now)
