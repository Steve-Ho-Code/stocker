"""Telegram commands displayed in the bot command menu."""

from telegram import BotCommand


BOT_COMMANDS = [
    BotCommand("start", "Show the current Stocker bot status"),
    BotCommand("update", "Fetch the latest stock price"),
    BotCommand("config_status", "Show the current bot configuration"),
    BotCommand("set_symbol", "Set the stock symbol to track"),
    BotCommand("set_timer", "Set the price update interval"),
    BotCommand("set_schedule_window", "Set the daily update schedule window"),
    BotCommand("set_schedule_timezone", "Set the schedule timezone"),
]
