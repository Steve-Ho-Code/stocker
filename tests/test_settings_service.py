from unittest.mock import MagicMock

import pytest

from src import config
from src.services import scheduler_service, settings_service


SCHEDULE_KEYS = {
    "frequency": "stocker:settings:schedule_frequency_minutes",
    "legacy": "stocker:settings:timer_interval",
    "start": "stocker:settings:schedule_start_time",
    "end": "stocker:settings:schedule_end_time",
    "timezone": "stocker:settings:schedule_timezone",
}


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.operations = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def set(self, key, value):
        self.operations.append(("set", key, value))
        return self

    def delete(self, key):
        self.operations.append(("delete", key, None))
        return self

    async def execute(self):
        self.redis.execute_count += 1
        if self.redis.execute_count in self.redis.fail_on_execute:
            raise RuntimeError(f"redis transaction failure {self.redis.execute_count}")

        updated = dict(self.redis.data)
        for operation, key, value in self.operations:
            if operation == "set":
                updated[key] = str(value)
            else:
                updated.pop(key, None)
        self.redis.data = updated
        if self.redis.execute_count in self.redis.fail_after_execute:
            raise RuntimeError(
                f"redis post-commit failure {self.redis.execute_count}"
            )
        return [True] * len(self.operations)


class FakeRedis:
    def __init__(
        self,
        data=None,
        fail_on_execute=None,
        fail_after_execute=None,
    ):
        self.data = dict(data or {})
        self.fail_on_execute = set(fail_on_execute or [])
        self.fail_after_execute = set(fail_after_execute or [])
        self.execute_count = 0

    async def mget(self, *keys):
        return [self.data.get(key) for key in keys]

    def pipeline(self, transaction=True):
        assert transaction is True
        return FakePipeline(self)


async def fake_callback(context):
    return None


@pytest.fixture
def old_schedule(mocker):
    mocker.patch.object(config.settings, "SCHEDULE_FREQUENCY_MINUTES", 5)
    mocker.patch.object(config.settings, "TIMER_INTERVAL", 300)
    mocker.patch.object(config.settings, "SCHEDULE_START_TIME", "09:30")
    mocker.patch.object(config.settings, "SCHEDULE_END_TIME", "16:00")
    mocker.patch.object(config.settings, "SCHEDULE_TIMEZONE", "UTC")
    return scheduler_service.ScheduleConfig(5, "09:30", "16:00", "UTC")


def persisted_schedule(schedule):
    return {
        SCHEDULE_KEYS["frequency"]: str(schedule.frequency_minutes),
        SCHEDULE_KEYS["legacy"]: str(schedule.frequency_minutes * 60),
        SCHEDULE_KEYS["start"]: schedule.start_time,
        SCHEDULE_KEYS["end"]: schedule.end_time,
        SCHEDULE_KEYS["timezone"]: schedule.timezone_name,
    }


@pytest.mark.asyncio
async def test_frequency_update_persists_and_reschedules_complete_candidate(
    mocker,
    old_schedule,
):
    redis = FakeRedis(persisted_schedule(old_schedule))
    mocker.patch.object(config, "redis_client", redis)
    mock_reschedule = mocker.patch(
        "src.services.settings_service.scheduler_service.reschedule_price_update"
    )
    job_queue = MagicMock()

    result = await settings_service.update_schedule_frequency_minutes(
        15,
        job_queue=job_queue,
        callback=fake_callback,
    )

    candidate = scheduler_service.ScheduleConfig(15, "09:30", "16:00", "UTC")
    assert result == candidate
    assert redis.data == persisted_schedule(candidate)
    assert config.settings.SCHEDULE_FREQUENCY_MINUTES == 15
    assert config.settings.TIMER_INTERVAL == 900
    mock_reschedule.assert_called_once_with(
        job_queue,
        fake_callback,
        schedule=candidate,
        rollback_schedule=old_schedule,
    )


@pytest.mark.asyncio
async def test_persistence_failure_restores_raw_redis_and_memory_without_reschedule(
    mocker,
    old_schedule,
):
    original = persisted_schedule(old_schedule)
    original.pop(SCHEDULE_KEYS["legacy"])
    redis = FakeRedis(original, fail_on_execute={1})
    mocker.patch.object(config, "redis_client", redis)
    mock_reschedule = mocker.patch(
        "src.services.settings_service.scheduler_service.reschedule_price_update"
    )

    with pytest.raises(settings_service.ScheduleUpdateError):
        await settings_service.update_schedule_frequency_minutes(
            15,
            job_queue=MagicMock(),
            callback=fake_callback,
        )

    assert redis.data == original
    assert config.settings.SCHEDULE_FREQUENCY_MINUTES == 5
    assert config.settings.TIMER_INTERVAL == 300
    mock_reschedule.assert_not_called()


@pytest.mark.asyncio
async def test_post_commit_error_compensates_to_exact_raw_snapshot(
    mocker,
    old_schedule,
):
    original = persisted_schedule(old_schedule)
    original.pop(SCHEDULE_KEYS["legacy"])
    redis = FakeRedis(original, fail_after_execute={1})
    mocker.patch.object(config, "redis_client", redis)
    mock_reschedule = mocker.patch(
        "src.services.settings_service.scheduler_service.reschedule_price_update"
    )

    with pytest.raises(settings_service.ScheduleUpdateError):
        await settings_service.update_schedule_frequency_minutes(
            15,
            job_queue=MagicMock(),
            callback=fake_callback,
        )

    assert redis.execute_count == 2
    assert redis.data == original
    assert SCHEDULE_KEYS["legacy"] not in redis.data
    assert scheduler_service.current_schedule_config() == old_schedule
    mock_reschedule.assert_not_called()


@pytest.mark.asyncio
async def test_reschedule_failure_restores_redis_memory_and_previous_jobs(
    mocker,
    old_schedule,
):
    original = persisted_schedule(old_schedule)
    redis = FakeRedis(original)
    mocker.patch.object(config, "redis_client", redis)
    mock_reschedule = mocker.patch(
        "src.services.settings_service.scheduler_service.reschedule_price_update",
        side_effect=scheduler_service.ScheduleRegistrationError(RuntimeError("add failed")),
    )
    job_queue = MagicMock()

    with pytest.raises(settings_service.ScheduleUpdateError):
        await settings_service.update_schedule_frequency_minutes(
            15,
            job_queue=job_queue,
            callback=fake_callback,
        )

    candidate = scheduler_service.ScheduleConfig(15, "09:30", "16:00", "UTC")
    mock_reschedule.assert_called_once_with(
        job_queue,
        fake_callback,
        schedule=candidate,
        rollback_schedule=old_schedule,
    )
    assert redis.execute_count == 2
    assert redis.data == original
    assert scheduler_service.current_schedule_config() == old_schedule


@pytest.mark.asyncio
async def test_missing_job_queue_rolls_back_persistence_and_memory(
    mocker,
    old_schedule,
):
    original = persisted_schedule(old_schedule)
    redis = FakeRedis(original)
    mocker.patch.object(config, "redis_client", redis)

    with pytest.raises(settings_service.ScheduleUpdateError):
        await settings_service.update_schedule_frequency_minutes(
            15,
            job_queue=None,
            callback=fake_callback,
        )

    assert redis.data == original
    assert scheduler_service.current_schedule_config() == old_schedule


@pytest.mark.asyncio
async def test_compensating_redis_failure_marks_degraded_and_preserves_effective_memory(
    mocker,
    old_schedule,
):
    redis = FakeRedis(persisted_schedule(old_schedule), fail_on_execute={2})
    mocker.patch.object(config, "redis_client", redis)
    mocker.patch(
        "src.services.settings_service.scheduler_service.reschedule_price_update",
        side_effect=scheduler_service.ScheduleRegistrationError(RuntimeError("add failed")),
    )

    with pytest.raises(settings_service.ScheduleUpdateRollbackError) as exc_info:
        await settings_service.update_schedule_frequency_minutes(
            15,
            job_queue=MagicMock(),
            callback=fake_callback,
        )

    assert isinstance(exc_info.value.primary_error, Exception)
    assert isinstance(exc_info.value.rollback_error, Exception)
    assert scheduler_service.current_schedule_config() == old_schedule
    assert scheduler_service.schedule_state() == scheduler_service.SCHEDULE_STATE_DEGRADED


@pytest.mark.asyncio
async def test_complete_candidate_is_validated_before_redis_or_jobs_change(
    mocker,
    old_schedule,
):
    redis = FakeRedis(persisted_schedule(old_schedule))
    mocker.patch.object(config, "redis_client", redis)
    mock_reschedule = mocker.patch(
        "src.services.settings_service.scheduler_service.reschedule_price_update"
    )

    with pytest.raises(Exception):
        await settings_service.update_schedule_window(
            "16:00",
            "16:00",
            job_queue=MagicMock(),
            callback=fake_callback,
        )

    assert redis.execute_count == 0
    assert redis.data == persisted_schedule(old_schedule)
    assert scheduler_service.current_schedule_config() == old_schedule
    mock_reschedule.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["window", "timezone"])
async def test_window_and_timezone_updates_use_same_atomic_coordinator(
    mocker,
    old_schedule,
    change,
):
    redis = FakeRedis(persisted_schedule(old_schedule))
    mocker.patch.object(config, "redis_client", redis)
    mock_reschedule = mocker.patch(
        "src.services.settings_service.scheduler_service.reschedule_price_update"
    )
    job_queue = MagicMock()

    if change == "window":
        result = await settings_service.update_schedule_window(
            "22:00",
            "02:00",
            job_queue=job_queue,
            callback=fake_callback,
        )
        expected = scheduler_service.ScheduleConfig(5, "22:00", "02:00", "UTC")
    else:
        result = await settings_service.update_schedule_timezone(
            "Asia/Hong_Kong",
            job_queue=job_queue,
            callback=fake_callback,
        )
        expected = scheduler_service.ScheduleConfig(
            5,
            "09:30",
            "16:00",
            "Asia/Hong_Kong",
        )

    assert result == expected
    assert redis.data == persisted_schedule(expected)
    mock_reschedule.assert_called_once_with(
        job_queue,
        fake_callback,
        schedule=expected,
        rollback_schedule=old_schedule,
    )
