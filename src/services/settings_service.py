from .. import config

async def update_symbol(new_symbol: str):
    """Updates the symbol in Redis."""
    await config.redis_client.set("stocker:settings:symbol", new_symbol)
    config.settings.SYMBOL = new_symbol # Update in-memory settings as well

async def update_timer_interval(new_interval: int):
    """Updates the timer interval in Redis."""
    await config.redis_client.set("stocker:settings:timer_interval", new_interval)
    config.settings.TIMER_INTERVAL = new_interval # Update in-memory settings as well
