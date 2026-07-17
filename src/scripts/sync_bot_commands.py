"""Synchronize Stocker's visible Telegram command menu."""

import asyncio
import logging

from telegram import Bot

from src import config
from src.bot.command_menu import BOT_COMMANDS


logging.basicConfig(level=logging.INFO)
# HTTPX request logs include the Bot API URL, which contains the bot token.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def sync_bot_commands() -> None:
    """Update Telegram's command menu only when definitions change."""
    async with Bot(token=config.settings.API_TOKEN) as bot:
        current_commands = await bot.get_my_commands()
        if list(current_commands) == BOT_COMMANDS:
            logger.info("Telegram command menu is already up to date.")
            return

        updated = await bot.set_my_commands(BOT_COMMANDS)
        if not updated:
            raise RuntimeError("Telegram rejected the command menu update.")

        logger.info("Telegram command menu updated successfully.")


async def main() -> None:
    """Run synchronization and convert failures into a safe non-zero exit."""
    try:
        await sync_bot_commands()
    except Exception:
        # Do not log the exception text: a lower-level error may contain the
        # token-bearing Telegram API URL.
        logger.error("Failed to synchronize Telegram bot commands.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    asyncio.run(main())
