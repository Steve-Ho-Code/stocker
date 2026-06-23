import redis.asyncio as redis
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict

class Settings(BaseSettings):
    # Logging Configuration
    LOG_LEVEL: str = "INFO"

    # Telegram Bot Configuration
    API_TOKEN: str
    CHANNEL_ID: str
    SUPER_ADMIN_TELEGRAM_ID: int = 0

    # Dynamic settings that can be changed at runtime
    MAX_TIMER_INTERVAL: int = 1440  # in minutes
    SYMBOL: str = "VOO"  # Default symbol
    TIMER_INTERVAL: int = 600  # Default interval in seconds

    # Redis Configuration
    REDIS_URL: str = "redis://localhost"

    # Database Configuration
    DATABASE_URL: str = "postgresql://user:password@localhost/stocker"

    # Financial API Configuration
    FINNHUB_API_KEY: str = ""
    ALPHA_VANTAGE_API_KEY: str = ""
    ACTIVE_PROVIDER: str = "finnhub" # Default provider

    model_config = ConfigDict(env_file=".env")

settings = Settings()

# Redis client instance
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def get_dynamic_settings() -> dict:
    """Retrieves dynamic settings from Redis."""
    symbol = await redis_client.get("stocker:settings:symbol") or "VOO"
    timer_interval = await redis_client.get("stocker:settings:timer_interval") or 60
    return {
        "SYMBOL": symbol,
        "TIMER_INTERVAL": int(timer_interval),
    }


async def load_settings_from_redis():
    """Loads dynamic settings from Redis into the global settings object."""
    dynamic_settings = await get_dynamic_settings()
    settings.SYMBOL = dynamic_settings["SYMBOL"]
    settings.TIMER_INTERVAL = dynamic_settings["TIMER_INTERVAL"]
