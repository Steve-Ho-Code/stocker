import os
import sys
from unittest.mock import AsyncMock, MagicMock

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
)


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
async def test_set_timer_accepts_supported_frequency(mocker):
    update = make_update()
    context = make_context(args=["15"])
    mock_update_frequency = mocker.patch(
        "src.bot.handlers.settings_service.update_schedule_frequency_minutes",
        new_callable=AsyncMock,
    )
    mock_reschedule = mocker.patch(
        "src.bot.handlers.scheduler_service.reschedule_price_update",
    )

    result = await set_timer.__wrapped__(update, context)

    mock_update_frequency.assert_awaited_once_with(15)
    mock_reschedule.assert_called_once()
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
    mock_reschedule = mocker.patch(
        "src.bot.handlers.scheduler_service.reschedule_price_update",
    )

    result = await receive_timer(update, context)

    mock_update_frequency.assert_awaited_once_with(5)
    mock_reschedule.assert_called_once()
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
    mock_reschedule = mocker.patch(
        "src.bot.handlers.scheduler_service.reschedule_price_update",
    )
    mocker.patch.object(config.settings, "SCHEDULE_TIMEZONE", "America/New_York")

    await set_schedule_window.__wrapped__(update, context)

    mock_update_window.assert_awaited_once_with("09:30", "16:00")
    mock_reschedule.assert_called_once()
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
async def test_set_schedule_timezone_updates_timezone(mocker):
    update = make_update()
    context = make_context(args=["Asia/Hong_Kong"])
    mock_update_timezone = mocker.patch(
        "src.bot.handlers.settings_service.update_schedule_timezone",
        new_callable=AsyncMock,
    )
    mock_reschedule = mocker.patch(
        "src.bot.handlers.scheduler_service.reschedule_price_update",
    )

    await set_schedule_timezone.__wrapped__(update, context)

    mock_update_timezone.assert_awaited_once_with("Asia/Hong_Kong")
    mock_reschedule.assert_called_once()
    update.message.reply_text.assert_called_once_with(
        "Schedule timezone has been updated to Asia/Hong_Kong."
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
        "- Schedule Timezone: America/New_York"
    )
    update.message.reply_text.assert_called_once_with(expected_message)
