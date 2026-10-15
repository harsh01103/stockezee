import pytest
import gzip
import json
import os
import time
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
from datetime import datetime

from market.instrument_resolver import InstrumentResolver

@pytest.fixture
def mock_cache_file(tmp_path):
    cache_path = tmp_path / "NSE.json.gz"
    
    # Create mock data
    mock_data = [
        {
            "segment": "NSE_FO",
            "instrument_type": "CE",
            "underlying_symbol": "NIFTY",
            "strike_price": 23000.0,
            # "26-Jun-2024" is 2024-06-26. Let's create an epoch MS for it.
            # Wait, epoch MS for 2024-06-26 00:00:00 UTC
            "expiry": int(datetime(2024, 6, 26).timestamp() * 1000),
            "instrument_key": "NSE_FO|12345"
        },
        {
            "segment": "NSE_FO",
            "instrument_type": "PE",
            "underlying_symbol": "BANKNIFTY",
            "strike_price": 50000.0,
            "expiry": int(datetime(2024, 6, 26).timestamp() * 1000),
            "instrument_key": "NSE_FO|67890"
        }
    ]
    
    with gzip.open(cache_path, "wt", encoding="utf-8") as f:
        json.dump(mock_data, f)
        
    return cache_path

@pytest.mark.asyncio
async def test_resolver_loads_and_resolves(mock_cache_file):
    resolver = InstrumentResolver()
    resolver.CACHE_FILE = mock_cache_file
    
    # Ensure loaded (should not download because file is fresh)
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        await resolver.ensure_loaded()
        mock_get.assert_not_called()
        
    assert resolver.is_loaded
    assert len(resolver.lookup_table) == 2
    
    # Test resolution
    key1 = resolver.resolve("NIFTY", "26-Jun-2024", 23000.0, "CE")
    assert key1 == "NSE_FO|12345"
    
    key2 = resolver.resolve("BANKNIFTY", "26-Jun-2024", 50000.0, "PE")
    assert key2 == "NSE_FO|67890"
    
    # Test missing
    key_missing = resolver.resolve("NIFTY", "26-Jun-2024", 99999.0, "CE")
    assert key_missing is None

@pytest.mark.asyncio
async def test_resolver_downloads_if_stale(mock_cache_file):
    resolver = InstrumentResolver()
    resolver.CACHE_FILE = mock_cache_file
    
    # Make file stale
    stale_time = time.time() - 90000 # 25 hours ago
    os.utime(mock_cache_file, (stale_time, stale_time))
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Just write empty gzip
        empty_gz = gzip.compress(b"[]")
        mock_response.content = empty_gz
        mock_get.return_value = mock_response
        
        await resolver.ensure_loaded()
        mock_get.assert_called_once()

def test_resolve_nearest_expiry_fallback():
    resolver = InstrumentResolver()
    resolver.lookup_table = {
        "NIFTY_2024-06-26_23500.0_CE": "NSE_FO|12345",
        "NIFTY_2024-07-04_23500.0_CE": "NSE_FO|67890",
    }
    resolver.expiries_by_underlying = {
        "NIFTY": {"2024-06-26", "2024-07-04"}
    }
    resolver.is_loaded = True
    
    # Requesting 27-Jun-2024, nearest available future is 04-Jul-2024
    key = resolver.resolve("NIFTY", "27-Jun-2024", 23500.0, "CE")
    assert key == "NSE_FO|67890"

def test_resolve_reject_synthetic_date():
    resolver = InstrumentResolver()
    resolver.lookup_table = {}
    resolver.expiries_by_underlying = {}
    resolver.is_loaded = True
    
    # Year 1970 should be rejected
    key = resolver.resolve("NIFTY", "01-Jan-1970", 23500.0, "CE")
    assert key is None
    
    # Year 2099 should be rejected
    key = resolver.resolve("NIFTY", "31-Dec-2099", 23500.0, "CE")
    assert key is None

def test_resolve_no_fallback_available():
    resolver = InstrumentResolver()
    resolver.lookup_table = {
        "NIFTY_2024-06-26_23500.0_CE": "NSE_FO|12345",
    }
    resolver.expiries_by_underlying = {
        "NIFTY": {"2024-06-26"}
    }
    resolver.is_loaded = True
    
    # Requesting 05-Jul-2024, no future expiries available
    key = resolver.resolve("NIFTY", "05-Jul-2024", 23500.0, "CE")
    assert key is None
