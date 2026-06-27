from datetime import datetime
from zoneinfo import ZoneInfo

from src import config
from src.services import scheduler_service


class FakeJob:
    def __init__(self):
        self.removed = False

    def schedule_removal(self):
        self.removed = True


class FakeJobQueue:
    def __init__(self, jobs=None):
        self.jobs = jobs or []
        self.run_custom_calls = []

    def get_jobs_by_name(self, name):
        return self.jobs if name == scheduler_service.PRICE_UPDATE_JOB_NAME else []

    def run_custom(self, callback, job_kwargs, name=None):
        self.run_custom_calls.append(
            {"callback": callback, "job_kwargs": job_kwargs, "name": name}
        )
        return FakeJob()


async def fake_callback(context):
    return None


def test_schedule_price_update_replaces_existing_job(mocker):
    mocker.patch.object(config.settings, "SCHEDULE_FREQUENCY_MINUTES", 15)
    mocker.patch.object(config.settings, "SCHEDULE_TIMEZONE", "UTC")
    existing_job = FakeJob()
    job_queue = FakeJobQueue(jobs=[existing_job])

    scheduler_service.schedule_price_update(job_queue, fake_callback)

    assert existing_job.removed is True
    assert len(job_queue.run_custom_calls) == 1
    assert job_queue.run_custom_calls[0]["name"] == scheduler_service.PRICE_UPDATE_JOB_NAME
    assert "trigger" in job_queue.run_custom_calls[0]["job_kwargs"]


def test_should_run_scheduled_update_inside_window(mocker):
    mocker.patch.object(config.settings, "SCHEDULE_START_TIME", "09:30")
    mocker.patch.object(config.settings, "SCHEDULE_END_TIME", "16:00")
    mocker.patch.object(config.settings, "SCHEDULE_TIMEZONE", "America/New_York")
    now = datetime(2026, 1, 1, 10, 0, tzinfo=ZoneInfo("America/New_York"))

    assert scheduler_service.should_run_scheduled_update(now)


def test_should_run_scheduled_update_outside_window(mocker):
    mocker.patch.object(config.settings, "SCHEDULE_START_TIME", "09:30")
    mocker.patch.object(config.settings, "SCHEDULE_END_TIME", "16:00")
    mocker.patch.object(config.settings, "SCHEDULE_TIMEZONE", "America/New_York")
    now = datetime(2026, 1, 1, 8, 0, tzinfo=ZoneInfo("America/New_York"))

    assert not scheduler_service.should_run_scheduled_update(now)
