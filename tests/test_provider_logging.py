import logging
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.providers import alpha_vantage, finnhub


def _mock_async_client(mocker, module, *, response=None, error=None):
    mock_get = AsyncMock(return_value=response, side_effect=error)
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = mock_get
    mocker.patch.object(module.httpx, "AsyncClient", return_value=mock_client)
    return mock_get


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("module", "setting_name", "query_name", "provider_name"),
    [
        (finnhub, "FINNHUB_API_KEY", "token", "finnhub"),
        (alpha_vantage, "ALPHA_VANTAGE_API_KEY", "apikey", "alpha_vantage"),
    ],
)
async def test_http_status_error_log_is_safe(
    mocker,
    caplog,
    module,
    setting_name,
    query_name,
    provider_name,
):
    secret = f"{provider_name}-http-status-secret"
    secret_url = (
        f"https://provider.test/quote?symbol=VOO&{query_name}={secret}"
    )
    request = httpx.Request("GET", secret_url)
    response = httpx.Response(502, request=request)
    mocker.patch.object(module.config.settings, setting_name, secret)
    _mock_async_client(mocker, module, response=response)

    with caplog.at_level(logging.ERROR, logger=module.__name__):
        result = await module.get_asset_price(use_cache=False)

    assert result is None
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.provider == provider_name
    assert record.http_status == 502
    assert record.exc_info is None
    assert "502" in record.getMessage()
    assert provider_name in record.getMessage()
    assert secret not in caplog.text
    assert secret_url not in caplog.text


@pytest.mark.asyncio
async def test_finnhub_request_error_log_is_safe(mocker, caplog):
    secret = "finnhub-request-error-secret"
    secret_url = f"https://finnhub.io/api/v1/quote?symbol=VOO&token={secret}"
    request = httpx.Request("GET", secret_url)
    error = httpx.ConnectTimeout(
        f"timed out while requesting {secret_url}",
        request=request,
    )
    mocker.patch.object(finnhub.config.settings, "FINNHUB_API_KEY", secret)
    _mock_async_client(mocker, finnhub, error=error)

    with caplog.at_level(logging.ERROR, logger=finnhub.__name__):
        result = await finnhub.get_asset_price(use_cache=False)

    assert result is None
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.provider == "finnhub"
    assert record.error_type == "ConnectTimeout"
    assert record.exc_info is None
    assert "ConnectTimeout" in record.getMessage()
    assert secret not in caplog.text
    assert secret_url not in caplog.text
