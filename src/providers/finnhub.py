import logging
import httpx
from typing import Optional, Dict
from aiocache import cached

from .. import config
from ._logging import log_provider_failure

logger = logging.getLogger(__name__)
PROVIDER_NAME = "finnhub"

@cached(ttl=60)
async def get_asset_price_cached() -> Optional[Dict[str, str]]:
    return await get_asset_price(use_cache=False)

async def get_asset_price(use_cache: bool = True) -> Optional[Dict[str, str]]:
    """Fetches the current price of the asset specified in the config from Finnhub."""
    if use_cache:
        return await get_asset_price_cached()

    url = f'https://finnhub.io/api/v1/quote?symbol={config.settings.SYMBOL}&token={config.settings.FINNHUB_API_KEY}'
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()  # Raise an exception for bad status codes
            data = response.json()
            
            # Finnhub returns 'c' for current price. If it's missing or 0, the symbol might be invalid.
            current_price = data.get("c")
            if current_price is None or current_price == 0:
                logger.error(
                    "Price provider returned invalid price data: provider=%s.",
                    PROVIDER_NAME,
                    extra={"provider": PROVIDER_NAME},
                )
                return {"error": "Invalid API call or symbol not found on Finnhub."}
            
            price_data = {
                "price": str(current_price),
                "change": str(data.get("d", "0.0")),
                "change_percent": str(data.get("dp", "0.0"))
            }
            return price_data
    except Exception as exc:
        log_provider_failure(logger, PROVIDER_NAME, exc)
    return None
