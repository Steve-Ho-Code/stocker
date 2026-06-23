import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from unittest.mock import AsyncMock, MagicMock
from src.bot.handlers import manual_update, config_status
from telegram import Bot

@pytest.mark.asyncio
async def test_manual_update_authorized(mocker):
    """Tests that an authorized user can trigger a manual update."""
    # Mock update and context
    update = MagicMock()
    update.message.from_user.id = 123
    context = MagicMock()
    context.bot = Bot(token="test-token") # Ensure context.bot is an instance of Bot

    # Mock config and send_price_update
    mocker.patch("src.bot.handlers.config.settings.AUTHORIZED_USER_IDS", "123,456")
    mock_send_update = mocker.patch("src.bot.handlers.send_price_update", new_callable=AsyncMock)

    # Call the function
    await manual_update(update, context)

    # Assertions
    mock_send_update.assert_called_once_with(context.bot, user_id=123)

@pytest.mark.asyncio
async def test_manual_update_unauthorized(mocker):
    """Tests that an unauthorized user is denied."""
    # Mock update and context
    update = MagicMock()
    update.message.from_user.id = 789
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    # Mock config and send_price_update
    mocker.patch("src.bot.handlers.config.settings.AUTHORIZED_USER_IDS", "123,456")
    mock_send_update = mocker.patch("src.bot.handlers.send_price_update", new_callable=AsyncMock)

    # Call the function
    await manual_update(update, context)

    # Assertions
    mock_send_update.assert_not_called()
    update.message.reply_text.assert_called_once_with("You are not authorized to use this command.")

@pytest.mark.asyncio
async def test_config_status_authorized(mocker):
    """Tests that an authorized user can view the configuration status."""
    # Mock update and context
    update = MagicMock()
    update.message.from_user.id = 123
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    # Mock config
    mocker.patch("src.bot.handlers.config.settings.AUTHORIZED_USER_IDS", "123,456")
    mocker.patch("src.bot.handlers.config.settings.SYMBOL", "TEST")
    mocker.patch("src.bot.handlers.config.settings.TIMER_INTERVAL", 300)

    # Call the function
    await config_status(update, context)

    # Assertions
    expected_message = (
        f"Current Bot Configuration:\n"
        f"- Symbol: TEST\n"
        f"- Timer Interval: 5 minute(s)"
    )
    update.message.reply_text.assert_called_once_with(expected_message)
