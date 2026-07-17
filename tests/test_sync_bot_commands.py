import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import BotCommand

from src.bot.command_menu import BOT_COMMANDS
from src.scripts import sync_bot_commands as sync_module


TEST_TOKEN = "123:test-token"


@pytest.fixture
def mocked_bot(mocker):
    bot = MagicMock()
    bot.__aenter__ = AsyncMock(return_value=bot)
    bot.__aexit__ = AsyncMock(return_value=None)
    bot.get_my_commands = AsyncMock()
    bot.set_my_commands = AsyncMock(return_value=True)

    bot_factory = mocker.patch.object(sync_module, "Bot", return_value=bot)
    mocker.patch.object(sync_module.config.settings, "API_TOKEN", TEST_TOKEN)
    return SimpleNamespace(bot=bot, factory=bot_factory)


def test_command_menu_contains_only_visible_commands():
    assert [
        (command.command, command.description) for command in BOT_COMMANDS
    ] == [
        ("start", "Show the current Stocker bot status"),
        ("update", "Fetch the latest stock price"),
        ("config_status", "Show the current bot configuration"),
        ("set_symbol", "Set the stock symbol to track"),
        ("set_timer", "Set the price update interval"),
        ("set_schedule_window", "Set the daily update schedule window"),
        ("set_schedule_timezone", "Set the schedule timezone"),
    ]
    assert all(isinstance(command, BotCommand) for command in BOT_COMMANDS)
    assert {command.command for command in BOT_COMMANDS}.isdisjoint(
        {"grant_admin", "cancel"}
    )


@pytest.mark.asyncio
async def test_matching_tuple_commands_are_not_rewritten(mocked_bot, caplog):
    # python-telegram-bot 22.x returns a tuple from get_my_commands().
    mocked_bot.bot.get_my_commands.return_value = tuple(BOT_COMMANDS)

    with caplog.at_level(logging.INFO, logger=sync_module.__name__):
        await sync_module.sync_bot_commands()

    mocked_bot.factory.assert_called_once_with(token=TEST_TOKEN)
    mocked_bot.bot.get_my_commands.assert_awaited_once_with()
    mocked_bot.bot.set_my_commands.assert_not_awaited()
    assert "Telegram command menu is already up to date." in caplog.text


@pytest.mark.asyncio
async def test_initial_sync_retrieves_then_sets_all_commands(
    mocked_bot,
    caplog,
):
    calls = []

    async def get_commands():
        calls.append("get")
        return ()

    async def set_commands(commands):
        calls.append("set")
        return True

    mocked_bot.bot.get_my_commands.side_effect = get_commands
    mocked_bot.bot.set_my_commands.side_effect = set_commands

    with caplog.at_level(logging.INFO, logger=sync_module.__name__):
        await sync_module.sync_bot_commands()

    assert calls == ["get", "set"]
    mocked_bot.bot.set_my_commands.assert_awaited_once_with(BOT_COMMANDS)
    assert "Telegram command menu updated successfully." in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current_commands",
    [
        pytest.param(
            (
                BotCommand("start", "An outdated description"),
                *BOT_COMMANDS[1:],
            ),
            id="description-changed",
        ),
        pytest.param(tuple(BOT_COMMANDS[:-1]), id="command-added-locally"),
        pytest.param(
            (*BOT_COMMANDS, BotCommand("obsolete", "An obsolete command")),
            id="command-removed-locally",
        ),
    ],
)
async def test_different_commands_are_updated(mocked_bot, current_commands):
    mocked_bot.bot.get_my_commands.return_value = current_commands

    await sync_module.sync_bot_commands()

    mocked_bot.bot.get_my_commands.assert_awaited_once_with()
    mocked_bot.bot.set_my_commands.assert_awaited_once_with(BOT_COMMANDS)


@pytest.mark.asyncio
async def test_rejected_command_update_raises(mocked_bot):
    mocked_bot.bot.get_my_commands.return_value = ()
    mocked_bot.bot.set_my_commands.return_value = False

    with pytest.raises(
        RuntimeError,
        match="Telegram rejected the command menu update",
    ):
        await sync_module.sync_bot_commands()

    mocked_bot.bot.set_my_commands.assert_awaited_once_with(BOT_COMMANDS)


@pytest.mark.asyncio
async def test_get_commands_api_failure_propagates(mocked_bot):
    error = RuntimeError("Telegram API unavailable")
    mocked_bot.bot.get_my_commands.side_effect = error

    with pytest.raises(RuntimeError) as caught:
        await sync_module.sync_bot_commands()

    assert caught.value is error
    mocked_bot.bot.set_my_commands.assert_not_awaited()


@pytest.mark.asyncio
async def test_main_logs_safe_failure_and_exits_nonzero(mocker, caplog):
    error_detail = f"request failed using {TEST_TOKEN}"
    mock_sync = mocker.patch.object(
        sync_module,
        "sync_bot_commands",
        new_callable=AsyncMock,
        side_effect=RuntimeError(error_detail),
    )

    with caplog.at_level(logging.ERROR, logger=sync_module.__name__):
        with pytest.raises(SystemExit) as caught:
            await sync_module.main()

    assert caught.value.code == 1
    mock_sync.assert_awaited_once_with()
    assert "Failed to synchronize Telegram bot commands." in caplog.text
    assert error_detail not in caplog.text
    assert TEST_TOKEN not in caplog.text
