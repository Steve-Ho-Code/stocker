import asyncio
import os
import sys
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest
from telegram import Bot
from telegram.ext import ConversationHandler

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import config
from src.bot.handlers import (
    TIMER,
    config_status,
    manual_update,
    receive_timer,
    set_schedule_timezone,
    set_schedule_window,
    set_timer,
    timer,
)
from src.services import scheduler_service, settings_service


def make_update(user_id=123, text=None):
    update = MagicMock()
    update.message.from_user.id = user_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


def make_context(args=None):
    context = MagicMock()
    context.args = args or []
    context.bot = Bot(token="123:ABC")
    context.job_queue = MagicMock()
    return context


def make_schedule():
    return scheduler_service.ScheduleConfig(15, "09:30", "16:00", "UTC")


class YieldingClaimRedis:
    def __init__(self, keys=None):
        self.keys = set(keys or [])

    async def set(self, key, value, **kwargs):
        await asyncio.sleep(0)
        if kwargs.get("nx") and key in self.keys:
            return None
        self.keys.add(key)
        return True


@pytest.mark.asyncio
async def test_manual_update_triggers_price_update(mocker):
    update = make_update(user_id=123)
    context = make_context()
    mock_send_update = mocker.patch(
        "src.bot.handlers.send_price_update",
        new_callable=AsyncMock,
    )

    await manual_update.__wrapped__(update, context)

    mock_send_update.assert_called_once_with(context.bot, user_id=123)


@pytest.mark.asyncio
async def test_manual_update_bypasses_schedule_claim(mocker):
    update = make_update(user_id=123)
    context = make_context()
    mocker.patch(
        "src.bot.handlers.send_price_update",
        new_callable=AsyncMock,
    )
    mock_claim = mocker.patch(
        "src.bot.handlers.scheduler_service.claim_scheduled_update",
        new_callable=AsyncMock,
    )
    mock_window = mocker.patch(
        "src.bot.handlers.scheduler_service.should_run_scheduled_update",
        return_value=False,
    )

    await manual_update.__wrapped__(update, context)

    mock_claim.assert_not_awaited()
    mock_window.assert_not_called()


@pytest.mark.asyncio
async def test_scheduled_timer_skips_duplicate_claim(mocker):
    context = make_context()
    now = object()
    schedule = make_schedule()
    mocker.patch(
        "src.bot.handlers.scheduler_service.current_schedule_datetime",
        return_value=now,
        create=True,
    )
    mocker.patch(
        "src.bot.handlers.scheduler_service.schedule_for_callback",
        return_value=schedule,
    )
    mock_window = mocker.patch(
        "src.bot.handlers.scheduler_service.should_run_scheduled_update",
        return_value=True,
    )
    mock_claim = mocker.patch(
        "src.bot.handlers.scheduler_service.claim_scheduled_update",
        new_callable=AsyncMock,
        return_value=False,
        create=True,
    )
    mock_send_update = mocker.patch(
        "src.bot.handlers.send_price_update",
        new_callable=AsyncMock,
    )

    await timer(context)

    mock_window.assert_called_once_with(now, schedule)
    mock_claim.assert_awaited_once_with(now, schedule)
    mock_send_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_scheduled_timer_sends_after_window_and_claim_checks(mocker):
    context = make_context()
    now = object()
    schedule = make_schedule()
    mocker.patch(
        "src.bot.handlers.scheduler_service.current_schedule_datetime",
        return_value=now,
        create=True,
    )
    mocker.patch(
        "src.bot.handlers.scheduler_service.schedule_for_callback",
        return_value=schedule,
    )
    mocker.patch(
        "src.bot.handlers.scheduler_service.should_run_scheduled_update",
        return_value=True,
    )
    mocker.patch(
        "src.bot.handlers.scheduler_service.claim_scheduled_update",
        new_callable=AsyncMock,
        return_value=True,
        create=True,
    )
    mock_send_update = mocker.patch(
        "src.bot.handlers.send_price_update",
        new_callable=AsyncMock,
    )

    await timer(context)

    mock_send_update.assert_awaited_once_with(context.bot)


@pytest.mark.asyncio
async def test_scheduled_timer_outside_window_does_not_claim_or_send(mocker):
    context = make_context()
    now = object()
    schedule = make_schedule()
    mocker.patch(
        "src.bot.handlers.scheduler_service.current_schedule_datetime",
        return_value=now,
    )
    mocker.patch(
        "src.bot.handlers.scheduler_service.schedule_for_callback",
        return_value=schedule,
    )
    mocker.patch(
        "src.bot.handlers.scheduler_service.should_run_scheduled_update",
        return_value=False,
    )
    mock_claim = mocker.patch(
        "src.bot.handlers.scheduler_service.claim_scheduled_update",
        new_callable=AsyncMock,
    )
    mock_send_update = mocker.patch(
        "src.bot.handlers.send_price_update",
        new_callable=AsyncMock,
    )

    await timer(context)

    mock_claim.assert_not_awaited()
    mock_send_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_scheduled_timer_rejects_stale_job_before_window_or_claim(mocker):
    context = make_context()
    context.job = object()
    now = object()
    mocker.patch(
        "src.bot.handlers.scheduler_service.current_schedule_datetime",
        return_value=now,
    )
    mock_fence = mocker.patch(
        "src.bot.handlers.scheduler_service.schedule_for_callback",
        return_value=None,
        create=True,
    )
    mock_window = mocker.patch(
        "src.bot.handlers.scheduler_service.should_run_scheduled_update",
        return_value=True,
    )
    mock_claim = mocker.patch(
        "src.bot.handlers.scheduler_service.claim_scheduled_update",
        new_callable=AsyncMock,
        return_value=True,
    )
    mock_send_update = mocker.patch(
        "src.bot.handlers.send_price_update",
        new_callable=AsyncMock,
    )

    await timer(context)

    mock_fence.assert_called_once_with(context.job, now)
    mock_window.assert_not_called()
    mock_claim.assert_not_awaited()
    mock_send_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_concurrent_scheduled_callbacks_send_once(mocker):
    context_a = make_context()
    context_b = make_context()
    now = datetime(2026, 1, 1, 10, 0, tzinfo=ZoneInfo("UTC"))
    schedule = make_schedule()
    mocker.patch.object(config.settings, "SCHEDULE_FREQUENCY_MINUTES", 15)
    mocker.patch.object(config.settings, "SCHEDULE_START_TIME", "09:30")
    mocker.patch.object(config.settings, "SCHEDULE_END_TIME", "16:00")
    mocker.patch.object(config.settings, "SCHEDULE_TIMEZONE", "UTC")
    mocker.patch.object(config, "redis_client", YieldingClaimRedis())
    mocker.patch(
        "src.bot.handlers.scheduler_service.current_schedule_datetime",
        return_value=now,
    )
    mocker.patch(
        "src.bot.handlers.scheduler_service.schedule_for_callback",
        return_value=schedule,
    )
    mock_send_update = mocker.patch(
        "src.bot.handlers.send_price_update",
        new_callable=AsyncMock,
    )

    await asyncio.gather(timer(context_a), timer(context_b))

    assert mock_send_update.await_count == 1


@pytest.mark.asyncio
async def test_recovered_process_does_not_resend_claimed_occurrence(mocker):
    context = make_context()
    now = datetime(2026, 1, 1, 10, 0, tzinfo=ZoneInfo("UTC"))
    schedule = make_schedule()
    claim_key = "stocker:schedule:sent:UTC:2026-01-01:10:00"
    mocker.patch.object(config.settings, "SCHEDULE_FREQUENCY_MINUTES", 15)
    mocker.patch.object(config.settings, "SCHEDULE_START_TIME", "09:30")
    mocker.patch.object(config.settings, "SCHEDULE_END_TIME", "16:00")
    mocker.patch.object(config.settings, "SCHEDULE_TIMEZONE", "UTC")
    mocker.patch.object(config, "redis_client", YieldingClaimRedis({claim_key}))
    mocker.patch(
        "src.bot.handlers.scheduler_service.current_schedule_datetime",
        return_value=now,
    )
    mocker.patch(
        "src.bot.handlers.scheduler_service.schedule_for_callback",
        return_value=schedule,
    )
    mock_send_update = mocker.patch(
        "src.bot.handlers.send_price_update",
        new_callable=AsyncMock,
    )

    await timer(context)

    mock_send_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_timer_accepts_supported_frequency(mocker):
    update = make_update()
    context = make_context(args=["15"])
    mock_update_frequency = mocker.patch(
        "src.bot.handlers.settings_service.update_schedule_frequency_minutes",
        new_callable=AsyncMock,
    )

    result = await set_timer.__wrapped__(update, context)

    mock_update_frequency.assert_awaited_once_with(
        15,
        job_queue=context.job_queue,
        callback=timer,
    )
    update.message.reply_text.assert_called_once_with(
        "Timer frequency has been updated to 15 minute(s)."
    )
    assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_set_timer_rejects_unsupported_frequency(mocker):
    update = make_update()
    context = make_context(args=["7"])
    mock_update_frequency = mocker.patch(
        "src.bot.handlers.settings_service.update_schedule_frequency_minutes",
        new_callable=AsyncMock,
    )

    result = await set_timer.__wrapped__(update, context)

    mock_update_frequency.assert_not_awaited()
    update.message.reply_text.assert_called_once_with(
        "Invalid frequency. Frequency must be one of: 1, 5, 10, 15, 30, 60 minutes."
    )
    assert result == TIMER


@pytest.mark.asyncio
async def test_receive_timer_accepts_supported_frequency(mocker):
    update = make_update(text="5")
    context = make_context()
    mock_update_frequency = mocker.patch(
        "src.bot.handlers.settings_service.update_schedule_frequency_minutes",
        new_callable=AsyncMock,
    )

    result = await receive_timer(update, context)

    mock_update_frequency.assert_awaited_once_with(
        5,
        job_queue=context.job_queue,
        callback=timer,
    )
    update.message.reply_text.assert_called_once_with(
        "Timer frequency has been updated to 5 minute(s)."
    )
    assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_set_schedule_window_updates_window(mocker):
    update = make_update()
    context = make_context(args=["09:30", "16:00"])
    mock_update_window = mocker.patch(
        "src.bot.handlers.settings_service.update_schedule_window",
        new_callable=AsyncMock,
    )
    mocker.patch.object(config.settings, "SCHEDULE_TIMEZONE", "America/New_York")

    await set_schedule_window.__wrapped__(update, context)

    mock_update_window.assert_awaited_once_with(
        "09:30",
        "16:00",
        job_queue=context.job_queue,
        callback=timer,
    )
    update.message.reply_text.assert_called_once_with(
        "Schedule window has been updated to 09:30-16:00 America/New_York."
    )


@pytest.mark.asyncio
async def test_set_schedule_window_rejects_invalid_window(mocker):
    update = make_update()
    context = make_context(args=["09:30", "09:30"])
    mock_update_window = mocker.patch(
        "src.bot.handlers.settings_service.update_schedule_window",
        new_callable=AsyncMock,
    )

    await set_schedule_window.__wrapped__(update, context)

    mock_update_window.assert_not_awaited()
    update.message.reply_text.assert_called_once_with(
        "Invalid schedule window. Start time and end time must be different."
    )


@pytest.mark.asyncio
async def test_set_schedule_window_rejects_invalid_time(mocker):
    update = make_update()
    context = make_context(args=["25:00", "16:00"])
    mock_update_window = mocker.patch(
        "src.bot.handlers.settings_service.update_schedule_window",
        new_callable=AsyncMock,
    )

    await set_schedule_window.__wrapped__(update, context)

    mock_update_window.assert_not_awaited()
    update.message.reply_text.assert_called_once_with(
        "Invalid schedule window. Time must use HH:MM format."
    )


@pytest.mark.asyncio
async def test_set_schedule_timezone_updates_timezone(mocker):
    update = make_update()
    context = make_context(args=["Asia/Hong_Kong"])
    mock_update_timezone = mocker.patch(
        "src.bot.handlers.settings_service.update_schedule_timezone",
        new_callable=AsyncMock,
    )

    await set_schedule_timezone.__wrapped__(update, context)

    mock_update_timezone.assert_awaited_once_with(
        "Asia/Hong_Kong",
        job_queue=context.job_queue,
        callback=timer,
    )
    update.message.reply_text.assert_called_once_with(
        "Schedule timezone has been updated to Asia/Hong_Kong."
    )


@pytest.mark.asyncio
async def test_set_schedule_timezone_rejects_invalid_iana_name(mocker):
    update = make_update()
    context = make_context(args=["New_York"])
    mock_update_timezone = mocker.patch(
        "src.bot.handlers.settings_service.update_schedule_timezone",
        new_callable=AsyncMock,
    )

    await set_schedule_timezone.__wrapped__(update, context)

    mock_update_timezone.assert_not_awaited()
    update.message.reply_text.assert_called_once_with(
        "Invalid timezone. Timezone must be a valid IANA timezone name."
    )


@pytest.mark.asyncio
async def test_config_status_includes_schedule_settings(mocker):
    update = make_update()
    context = make_context()
    mocker.patch.object(config.settings, "SYMBOL", "TEST")
    mocker.patch.object(config.settings, "SCHEDULE_FREQUENCY_MINUTES", 5)
    mocker.patch.object(config.settings, "SCHEDULE_START_TIME", "09:30")
    mocker.patch.object(config.settings, "SCHEDULE_END_TIME", "16:00")
    mocker.patch.object(config.settings, "SCHEDULE_TIMEZONE", "America/New_York")

    await config_status.__wrapped__(update, context)

    expected_message = (
        "Current Bot Configuration:\n"
        "- Symbol: TEST\n"
        "- Timer Frequency: 5 minute(s)\n"
        "- Schedule Window: 09:30-16:00\n"
        "- Schedule Timezone: America/New_York\n"
        "- Scheduling State: active"
    )
    update.message.reply_text.assert_called_once_with(expected_message)


@pytest.mark.asyncio
async def test_config_status_exposes_degraded_scheduler_state(mocker):
    update = make_update()
    context = make_context()
    scheduler_service.mark_schedule_degraded()

    await config_status.__wrapped__(update, context)

    assert "- Scheduling State: degraded" in update.message.reply_text.call_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "args"),
    [
        (set_timer, ["15"]),
        (set_schedule_window, ["09:30", "16:00"]),
        (set_schedule_timezone, ["UTC"]),
        (config_status, []),
    ],
)
async def test_schedule_commands_reject_non_admin_users(mocker, handler, args):
    update = make_update(user_id=123)
    context = make_context(args=args)
    user = SimpleNamespace(
        telegram_id=123,
        username="non-admin",
        is_admin=False,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=db)
    session.__aexit__ = AsyncMock(return_value=False)
    mocker.patch("src.bot.handlers.SessionLocal", return_value=session)

    await handler(update, context)

    update.message.reply_text.assert_called_once_with(
        "You are not authorized to use this command."
    )


@pytest.mark.asyncio
async def test_authorized_admin_can_update_timer_through_decorator(mocker):
    update = make_update(user_id=123)
    context = make_context(args=["15"])
    user = SimpleNamespace(
        telegram_id=123,
        username="admin",
        is_admin=True,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=db)
    session.__aexit__ = AsyncMock(return_value=False)
    mocker.patch("src.bot.handlers.SessionLocal", return_value=session)
    mock_update_frequency = mocker.patch(
        "src.bot.handlers.settings_service.update_schedule_frequency_minutes",
        new_callable=AsyncMock,
    )

    handler_result = await set_timer(update, context)

    mock_update_frequency.assert_awaited_once_with(
        15,
        job_queue=context.job_queue,
        callback=timer,
    )
    assert handler_result == ConversationHandler.END


@pytest.mark.asyncio
async def test_set_timer_reports_restored_previous_schedule_on_update_failure(mocker):
    update = make_update()
    context = make_context(args=["15"])
    mocker.patch(
        "src.bot.handlers.settings_service.update_schedule_frequency_minutes",
        new_callable=AsyncMock,
        side_effect=settings_service.ScheduleUpdateError(RuntimeError("failed")),
    )

    result = await set_timer.__wrapped__(update, context)

    update.message.reply_text.assert_called_once_with(
        "Schedule update failed; previous settings remain active."
    )
    assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_set_timer_reports_degraded_state_when_rollback_fails(mocker):
    update = make_update()
    context = make_context(args=["15"])
    mocker.patch(
        "src.bot.handlers.settings_service.update_schedule_frequency_minutes",
        new_callable=AsyncMock,
        side_effect=settings_service.ScheduleUpdateRollbackError(
            RuntimeError("failed"),
            RuntimeError("rollback failed"),
        ),
    )

    result = await set_timer.__wrapped__(update, context)

    update.message.reply_text.assert_called_once_with(
        "Schedule update failed and rollback was incomplete. "
        "Scheduling is degraded; check the logs."
    )
    assert result == ConversationHandler.END
