import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from market.nse_client import NSEClient
import httpx
import os

@pytest.fixture
def nse_client():
    # Force test URL
    os.environ["NSE_API_URL"] = "https://mock.nse.local/api"
    client = NSEClient(ttl_sec=20)
    # Mock ensure_cookies to avoid network calls
    client._ensure_cookies = AsyncMock()
    return client

@pytest.mark.asyncio
async def test_nse_config_driven_endpoint(nse_client):
    """Verify that the configured NSE_API_URL is used."""
    assert nse_client.api_url == "https://mock.nse.local/api"
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"records": {"data": [{"strikePrice": 100}]}}
        mock_get.return_value = mock_response
        
        data = await nse_client.get_option_chain("NIFTY")
        
        mock_get.assert_called_once_with("https://mock.nse.local/api?symbol=NIFTY")
        assert data is not None

@pytest.mark.asyncio
async def test_nse_schema_rejection_empty_universe(nse_client):
    """Verify that a response with an empty strike universe is rejected."""
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Empty data array
        mock_response.json.return_value = {"records": {"data": []}}
        mock_get.return_value = mock_response
        
        data = await nse_client.get_option_chain("NIFTY")
        
        # Should return None because it raised ValueError which was caught and there's no cache
        assert data is None

@pytest.mark.asyncio
async def test_nse_cache_fallback(nse_client):
    """Verify aggressive cache fallback on 404 or empty response."""
    # Pre-populate cache
    nse_client.cache["NIFTY"] = {"records": {"data": [{"strikePrice": 5000}]}}
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        # Simulate 404
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError("404", request=MagicMock(), response=mock_response)
        mock_get.return_value = mock_response
        
        # The TTL logic requires `now - last_fetch_time >= ttl_sec` to trigger a fetch.
        # So we don't set `last_fetch_time` meaning it forces a fetch which fails.
        data = await nse_client.get_option_chain("NIFTY")
        
        # Should return the cached data despite the 404
        assert data is not None
        assert data["records"]["data"][0]["strikePrice"] == 5000
