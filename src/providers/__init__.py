from . import alpha_vantage
from . import finnhub
from .. import config
import logging

logger = logging.getLogger(__name__)

async def get_asset_price(use_cache: bool = True):
    """
    Router function that directs the request to the active financial data provider.
    """
    provider = config.settings.ACTIVE_PROVIDER.lower()
    
    if provider == "finnhub":
        return await finnhub.get_asset_price(use_cache=use_cache)
    elif provider == "alpha_vantage":
        return await alpha_vantage.get_asset_price(use_cache=use_cache)
    else:
        logger.error(f"Unknown ACTIVE_PROVIDER configured: {provider}. Falling back to Alpha Vantage.")
        return await alpha_vantage.get_asset_price(use_cache=use_cache)