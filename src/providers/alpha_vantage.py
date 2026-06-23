import logging
import httpx
from typing import Optional, Dict
from aiocache import cached

from .. import config

logger = logging.getLogger(__name__)

@cached(ttl=60)
async def get_asset_price_cached() -> Optional[Dict[str, str]]:
    return await get_asset_price(use_cache=False)

async def get_asset_price(use_cache: bool = True) -> Optional[Dict[str, str]]:
    """Fetches the current price of the asset specified in the config from Alpha Vantage."""
    if use_cache:
        return await get_asset_price_cached()

    url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={config.settings.SYMBOL}&apikey={config.settings.ALPHA_VANTAGE_API_KEY}'
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()  # Raise an exception for bad status codes
            data = response.json()
            global_quote = data.get("Global Quote")
            if not global_quote:
                logger.error(f"API did not return Global Quote. Full response: {data}")
                error_msg = data.get("Information") or data.get("Note") or data.get("Error Message") or "Invalid API call or symbol not found."
                return {"error": error_msg}
            
            price_data = {
                "price": global_quote.get("05. price"),
                "change": global_quote.get("09. change"),
                "change_percent": global_quote.get("10. change percent")
            }
            return price_data
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e}")
    except httpx.RequestError as e:
        logger.error(f"An error occurred while requesting data: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
    return None
