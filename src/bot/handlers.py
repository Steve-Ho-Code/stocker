import logging
from functools import wraps
from telegram import Bot, Update
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy import select

from ..database import SessionLocal
from ..models import User
from ..services import schedule_rules, scheduler_service, settings_service
from ..providers import get_asset_price
from .. import config

logger = logging.getLogger(__name__)

# Conversation states
SYMBOL, TIMER = range(2)

def authorized_users_only(func):
    """Decorator to restrict access to authorized users based on DB."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        telegram_user = update.message.from_user
        if not telegram_user:
            logger.warning("Could not get user from message.")
            return

        async with SessionLocal() as db:
            try:
                user = (await db.execute(select(User).filter(User.telegram_id == telegram_user.id))).scalar_one_or_none()

                if not user:
                    logger.info(f"User with telegram_id {telegram_user.id} not found. Creating new user.")
                    new_user = User(
                        telegram_id=telegram_user.id,
                        username=telegram_user.username,
                        is_admin=False  # New users are not admins by default
                    )
                    db.add(new_user)
                    await db.commit()
                    await db.refresh(new_user) # Refresh to get the new user object with its ID
                    logger.info(f"New user '{new_user.username}' with telegram_id: {new_user.telegram_id} created successfully.")
                    user = new_user

                # Re-check authorization after potentially creating a user
                if not user.is_admin:
                    logger.warning(f"Unauthorized access attempt by user: {user.username} (ID: {user.telegram_id})")
                    await update.message.reply_text("You are not authorized to use this command.")
                    return

                return await func(update, context, *args, **kwargs)

            except Exception as e:
                logger.error(f"Database error in authorized_users_only for user {telegram_user.id}: {e}", exc_info=True)
                await db.rollback()
                await update.message.reply_text("A database error occurred. Please try again later.")
                return
    return wrapper

def super_admin_only(func):
    """Decorator to restrict access to the super admin."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.message.from_user.id
        if str(user_id) != str(config.settings.SUPER_ADMIN_TELEGRAM_ID):
            logger.warning(f"Unauthorized super admin command attempt by user_id: {user_id}")
            await update.message.reply_text("This command is restricted to the super admin.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

async def report_schedule_update_error(update: Update, exc: Exception) -> None:
    if isinstance(exc, settings_service.ScheduleUpdateRollbackError):
        logger.error(
            "Schedule update failed and rollback was incomplete: %s",
            exc,
            exc_info=True,
        )
        await update.message.reply_text(
            "Schedule update failed and rollback was incomplete. "
            "Scheduling is degraded; check the logs."
        )
        return

    logger.error("Schedule update failed and was restored: %s", exc, exc_info=True)
    await update.message.reply_text(
        "Schedule update failed; previous settings remain active."
    )

@super_admin_only
async def grant_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grants admin privileges to a user."""
    if not context.args:
        await update.message.reply_text("Usage: /grant_admin <telegram_user_id>")
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID. Please provide a number.")
        return

    async with SessionLocal() as db:
        try:
            user_to_grant = (await db.execute(select(User).filter(User.telegram_id == target_user_id))).scalar_one_or_none()
            if not user_to_grant:
                await update.message.reply_text(f"User with ID {target_user_id} not found. They must interact with the bot once to be registered.")
                return

            if user_to_grant.is_admin:
                await update.message.reply_text(f"User {target_user_id} is already an admin.")
                return

            user_to_grant.is_admin = True
            await db.commit()
            await db.refresh(user_to_grant) # Refresh to reflect the change

            logger.info(f"Admin privileges granted to user {user_to_grant.username} (ID: {target_user_id}) by super admin {update.message.from_user.id}")
            await update.message.reply_text(f"User {user_to_grant.username} (ID: {target_user_id}) has been granted admin privileges.")

        except Exception as e:
            logger.error(f"Database error in grant_admin for target_user_id {target_user_id}: {e}", exc_info=True)
            await db.rollback()
            await update.message.reply_text("A database error occurred while trying to grant admin privileges.")

async def send_price_update(bot: Bot, user_id: int = None):
    """Sends the asset price to the Telegram channel, or errors to the user."""
    price_data = await get_asset_price()
    if price_data and "error" in price_data:
        # API returned an error (e.g., rate limit, invalid symbol)
        error_msg = f"API Error fetching {config.settings.SYMBOL}: {price_data['error']}"
        logger.error(error_msg, extra={'user_id': user_id})
        if user_id:
             await bot.send_message(chat_id=user_id, text=error_msg)
        else:
            # Also send to channel if it's a scheduled update
            await bot.send_message(chat_id=config.settings.CHANNEL_ID, text=error_msg)
    elif price_data and price_data.get("price"):
        price = float(price_data["price"])
        change = float(price_data["change"])
        change_percent = float(price_data["change_percent"].replace('%',''))
        change_sign = "+" if change > 0 else ""
        message = (
            f"{config.settings.SYMBOL}: ${price:.2f}\n"
            f"{change_sign}{change:.2f} ({change_sign}{change_percent:.2f}%)"
        )
        await bot.send_message(chat_id=config.settings.CHANNEL_ID, text=message)
    else:
        logger.error(f"Could not fetch price for {config.settings.SYMBOL}. No error message from API.")
        # Only send generic failure message to the channel if it's the scheduled timer
        if not user_id:
            await bot.send_message(chat_id=config.settings.CHANNEL_ID, text=f"Failed to fetch price for {config.settings.SYMBOL}. Please try again later.")
        else:
            await bot.send_message(chat_id=user_id, text=f"Failed to fetch price for {config.settings.SYMBOL}. Please try again later.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when the /start command is issued and registers the user."""
    if update.message and update.message.from_user:
        telegram_user = update.message.from_user

        # 檢查並將新使用者加入資料庫
        async with SessionLocal() as db:
            try:
                user = (await db.execute(select(User).filter(User.telegram_id == telegram_user.id))).scalar_one_or_none()

                if not user:
                    logger.info(f"User with telegram_id {telegram_user.id} not found on /start. Creating new user.")
                    new_user = User(
                        telegram_id=telegram_user.id,
                        username=telegram_user.username,
                        is_admin=False
                    )
                    db.add(new_user)
                    await db.commit()
                    logger.info(f"New user '{new_user.username}' with telegram_id: {new_user.telegram_id} registered via /start.")
            except Exception as e:
                logger.error(f"Database error registering user {telegram_user.id} on /start: {e}", exc_info=True)
                await db.rollback()

        timer_frequency = config.settings.SCHEDULE_FREQUENCY_MINUTES
        interval_text = f"{timer_frequency} minute{'s' if timer_frequency != 1 else ''}"
        await update.message.reply_text(f"Hello! I am a bot that tracks {config.settings.SYMBOL}. I will send updates to the channel every {interval_text}.")

@authorized_users_only
async def manual_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually triggers a price update."""
    if isinstance(context.bot, Bot) and update.message:
        await send_price_update(context.bot, user_id=update.message.from_user.id)

@authorized_users_only
async def set_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets the stock symbol to track."""
    if not context.args:
        await update.message.reply_text("Please enter the stock symbol.")
        return SYMBOL

    new_symbol = context.args[0].upper()
    await settings_service.update_symbol(new_symbol)
    await update.message.reply_text(f"Symbol has been updated to {new_symbol}.")
    return ConversationHandler.END

async def receive_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the symbol from the user."""
    new_symbol = update.message.text.upper()
    await settings_service.update_symbol(new_symbol)
    await update.message.reply_text(f"Symbol has been updated to {new_symbol}.")
    return ConversationHandler.END

@authorized_users_only
async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets the timer interval for price updates."""
    if not context.args:
        await update.message.reply_text(
            "Please enter the timer frequency in minutes. "
            f"Supported values: {schedule_rules.supported_frequencies_text()}."
        )
        return TIMER

    try:
        frequency = schedule_rules.normalize_frequency(context.args[0])
        await settings_service.update_schedule_frequency_minutes(
            frequency,
            job_queue=context.job_queue,
            callback=timer,
        )

        await update.message.reply_text(
            f"Timer frequency has been updated to {frequency} minute(s)."
        )
        return ConversationHandler.END

    except settings_service.ScheduleUpdateError as exc:
        await report_schedule_update_error(update, exc)
        return ConversationHandler.END
    except (IndexError, schedule_rules.ScheduleValidationError) as exc:
        await update.message.reply_text(
            f"Invalid frequency. {exc}"
        )
        return TIMER

async def receive_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the timer from the user."""
    try:
        frequency = schedule_rules.normalize_frequency(update.message.text)
        await settings_service.update_schedule_frequency_minutes(
            frequency,
            job_queue=context.job_queue,
            callback=timer,
        )

        await update.message.reply_text(
            f"Timer frequency has been updated to {frequency} minute(s)."
        )
        return ConversationHandler.END

    except settings_service.ScheduleUpdateError as exc:
        await report_schedule_update_error(update, exc)
        return ConversationHandler.END
    except (IndexError, schedule_rules.ScheduleValidationError) as exc:
        await update.message.reply_text(
            f"Invalid frequency. {exc}"
        )
        return TIMER

@authorized_users_only
async def set_schedule_window(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets the daily active window for scheduled price updates."""
    if len(context.args) != 2:
        await update.message.reply_text(
            "Usage: /set_schedule_window <START_HH:MM> <END_HH:MM>"
        )
        return

    try:
        start_time, end_time = schedule_rules.validate_schedule_window(
            context.args[0],
            context.args[1],
        )
        await settings_service.update_schedule_window(
            start_time,
            end_time,
            job_queue=context.job_queue,
            callback=timer,
        )
        await update.message.reply_text(
            f"Schedule window has been updated to {start_time}-{end_time} "
            f"{config.settings.SCHEDULE_TIMEZONE}."
        )
    except settings_service.ScheduleUpdateError as exc:
        await report_schedule_update_error(update, exc)
    except schedule_rules.ScheduleValidationError as exc:
        await update.message.reply_text(f"Invalid schedule window. {exc}")

@authorized_users_only
async def set_schedule_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets the timezone used by scheduled price updates."""
    if len(context.args) != 1:
        await update.message.reply_text(
            "Usage: /set_schedule_timezone <IANA_TIMEZONE>"
        )
        return

    try:
        timezone = schedule_rules.normalize_timezone(context.args[0])
        await settings_service.update_schedule_timezone(
            timezone,
            job_queue=context.job_queue,
            callback=timer,
        )
        await update.message.reply_text(
            f"Schedule timezone has been updated to {timezone}."
        )
    except settings_service.ScheduleUpdateError as exc:
        await report_schedule_update_error(update, exc)
    except schedule_rules.ScheduleValidationError as exc:
        await update.message.reply_text(f"Invalid timezone. {exc}")

@authorized_users_only
async def config_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the current configuration of the bot."""
    symbol = config.settings.SYMBOL
    message = (
        f"Current Bot Configuration:\n"
        f"- Symbol: {symbol}\n"
        f"- Timer Frequency: {config.settings.SCHEDULE_FREQUENCY_MINUTES} minute(s)\n"
        f"- Schedule Window: {config.settings.SCHEDULE_START_TIME}-{config.settings.SCHEDULE_END_TIME}\n"
        f"- Schedule Timezone: {config.settings.SCHEDULE_TIMEZONE}\n"
        f"- Scheduling State: {scheduler_service.schedule_state()}"
    )
    await update.message.reply_text(message)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels and ends the conversation."""
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

async def timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles conversation timeout."""
    await update.message.reply_text("Request timed out. Please try again.")
    return ConversationHandler.END

async def timer(context: ContextTypes.DEFAULT_TYPE):
    """The function called by the job queue."""
    if isinstance(context.bot, Bot):
        now = scheduler_service.current_schedule_datetime()
        schedule = scheduler_service.schedule_for_callback(context.job, now)
        if schedule is None:
            logger.info(
                "Skipping stale or invalid scheduled price update callback: "
                "job=%s, time=%s",
                getattr(context.job, "name", None),
                now,
            )
            return
        if not scheduler_service.should_run_scheduled_update(now, schedule):
            logger.info(
                "Skipping scheduled price update outside active window: %s",
                scheduler_service.schedule_summary(schedule),
            )
            return
        if not await scheduler_service.claim_scheduled_update(now, schedule):
            logger.info(
                "Skipping duplicate or unclaimed scheduled price update: %s",
                scheduler_service.schedule_summary(schedule),
            )
            return
        await send_price_update(context.bot)
