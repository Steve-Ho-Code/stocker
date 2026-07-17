# main.py

import logging
import asyncio
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters

from src import config
from src.bot.handlers import (
    start, manual_update, set_symbol, receive_symbol, 
    set_timer, receive_timer, timer, cancel, SYMBOL, TIMER, timeout, config_status,
    grant_admin, set_schedule_window, set_schedule_timezone
)
from src.services import scheduler_service
from src.logging_config import configure_logging

logger = logging.getLogger(__name__)

def main() -> None:
    """Starts the bot."""

    configure_logging(
        level=config.settings.LOG_LEVEL,
        sensitive_values=(
            config.settings.API_TOKEN,
            config.settings.FINNHUB_API_KEY,
            config.settings.ALPHA_VANTAGE_API_KEY,
            config.settings.DATABASE_URL,
            config.settings.REDIS_URL,
        ),
    )
    # HTTPX INFO records contain request URLs; avoid recording them at all.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Create a new event loop to run the async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Load dynamic settings from Redis
    loop.run_until_complete(config.load_settings_from_redis())
    
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(config.settings.API_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("update", manual_update))
    application.add_handler(CommandHandler("config_status", config_status))
    application.add_handler(CommandHandler("grant_admin", grant_admin))
    application.add_handler(CommandHandler("set_schedule_window", set_schedule_window))
    application.add_handler(CommandHandler("set_schedule_timezone", set_schedule_timezone))

    # Add conversation handlers
    symbol_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("set_symbol", set_symbol)],
        states={
            SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_symbol)],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, timeout)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=60,
    )
    timer_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("set_timer", set_timer)],
        states={
            TIMER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_timer)],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, timeout)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=60,
    )

    application.add_handler(symbol_conv_handler)
    application.add_handler(timer_conv_handler)

    # Schedule the price update job
    job_queue = application.job_queue
    scheduler_service.schedule_price_update(job_queue, timer)

    # Start the bot using run_polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
