import pytest
import time
import os
import polars as pl
from market.storage import StorageManager
from market.schema import MarketTick

@pytest.mark.asyncio
async def test_storage_flush(tmp_path):
    import market.storage
    market.storage.RAW_DIR = tmp_path / "raw"
    market.storage.EVENTS_DIR = tmp_path / "events"
    
    storage = StorageManager()
    
    # Add fake ticks
    tick = MarketTick(
        timestamp=time.time() * 1000,
        exchange_timestamp=time.time() * 1000,
        underlying="NIFTY",
        expiry="2026-06-25",
        strike=23000.0,
        option_type="CE",
        spot=23000.0,
        ltp=100.0,
        bid=99.0,
        ask=101.0,
        volume=10,
        oi=1000,
        source="upstox",
        latency_ms=10.0,
        record_id="test_rec_1"
    )
    await storage.add_tick(tick)
    
    # Add fake event
    await storage.add_raw_event("upstox", b"dummy_payload")
    
    # Flush
    await storage.flush()
    
    # Verify files created
    raw_files = list((tmp_path / "raw").glob("**/*.parquet"))
    event_files = list((tmp_path / "events").glob("**/*.parquet"))
    
    assert len(raw_files) > 0
    assert len(event_files) > 0
    
    # Read and verify content
    df_raw = pl.read_parquet(raw_files[0])
    assert len(df_raw) == 1
    assert df_raw["record_id"][0] == "test_rec_1"
    
    df_event = pl.read_parquet(event_files[0])
    assert len(df_event) == 1
    assert df_event["source"][0] == "upstox"
