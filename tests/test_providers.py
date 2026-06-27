import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from unittest.mock import AsyncMock, MagicMock
from src.providers.alpha_vantage import get_asset_price
import httpx

@pytest.mark.asyncio
async def test_get_asset_price_success(mocker):
    """Tests the get_asset_price function in a success scenario."""
    # Mock the response object that client.get() will produce
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "Global Quote": {
            "05. price": "123.45",
            "09. change": "1.23",
            "10. change percent": "1.00%"
        }
    }
    mock_response.raise_for_status.return_value = None

    # Mock the client.get() coroutine to return the mock_response
    mock_get = AsyncMock(return_value=mock_response)
    
    # Mock the AsyncClient context manager
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.__aenter__.return_value.get = mock_get
    mocker.patch('httpx.AsyncClient', return_value=mock_client)

    # Call the function
    price_data = await get_asset_price(use_cache=False)

    # Assert the results
    assert price_data is not None
    assert price_data["price"] == "123.45"
    assert price_data["change"] == "1.23"
    assert price_data["change_percent"] == "1.00%"

@pytest.mark.asyncio
async def test_get_asset_price_http_error(mocker):
    """Tests the get_asset_price function when an HTTP error occurs."""
    # Mock the client.get() coroutine to raise an error
    mock_get = AsyncMock(side_effect=httpx.HTTPStatusError("Error", request=MagicMock(), response=MagicMock()))
    
    # Mock the AsyncClient context manager
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.__aenter__.return_value.get = mock_get
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    # Call the function
    price_data = await get_asset_price(use_cache=False)

    # Assert the results
    assert price_data is None

@pytest.mark.asyncio
async def test_get_asset_price_no_global_quote(mocker):
    """Tests the get_asset_price function when the 'Global Quote' is missing."""
    # Mock the response object that client.get() will produce
    mock_response = MagicMock()
    mock_response.json.return_value = {"Information": "Some info"}
    mock_response.raise_for_status.return_value = None

    # Mock the client.get() coroutine to return the mock_response
    mock_get = AsyncMock(return_value=mock_response)
    
    # Mock the AsyncClient context manager
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.__aenter__.return_value.get = mock_get
    mocker.patch('httpx.AsyncClient', return_value=mock_client)

    # Call the function
    price_data = await get_asset_price(use_cache=False)

    # Assert the results
    assert price_data is not None
    assert "error" in price_data
    assert price_data["error"] == "Some info"
