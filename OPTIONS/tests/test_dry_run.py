import pytest
import asyncio
from market.storage import StorageManager
from market.schema import MarketTick
import time

@pytest.mark.asyncio
async def test_dry_run_disables_storage():
    storage = StorageManager(dry_run=True)
    
    # Add a mock tick
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
        record_id="dry_run_test"
    )
    
    # add_tick is async
    await storage.add_tick(tick)
    assert len(storage.tick_buffer) == 1
    
    # add_raw_event should be skipped in dry_run
    await storage.add_raw_event("upstox", b"dummy")
    assert len(storage.event_buffer) == 0
    
    # flush should clear buffers without writing files
    await storage.flush()
    assert len(storage.tick_buffer) == 0
    assert len(storage.event_buffer) == 0
