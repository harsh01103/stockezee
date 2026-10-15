import pytest
import os
import time
import asyncio
from pathlib import Path
import polars as pl

from market.schema import MarketTick
from market.storage import StorageManager

@pytest.mark.asyncio
async def test_recovery_after_crash(tmp_path):
    """
    Test scenario:
    1. Start recorder (simulate with StorageManager)
    2. Collect 2 mins of data
    3. Kill process (simulate by abandoning the instance without closing gracefully)
    4. Restart
    5. Verify no parquet corruption and missing rows < 0.5%
    """
    # Override storage dirs for test
    import market.storage
    original_raw = market.storage.RAW_DIR
    original_events = market.storage.EVENTS_DIR
    
    test_raw = tmp_path / "raw"
    test_events = tmp_path / "events"
    market.storage.RAW_DIR = test_raw
    market.storage.EVENTS_DIR = test_events
    
    try:
        storage1 = StorageManager()
        
        # Simulate 2 mins of data (say 1000 ticks, flushing every 10s)
        # We will write some ticks, flush, write more, flush
        for i in range(12): # 12 flushes of 10s = 120s
            for j in range(100):
                tick = MarketTick(
                    timestamp=time.time() * 1000,
                    exchange_timestamp=time.time() * 1000,
                    underlying="NIFTY",
                    expiry="2026-06-25",
                    strike=23000.0,
                    option_type="CE",
                    spot=23000.0,
                    ltp=100.0 + i,
                    bid=99.0,
                    ask=101.0,
                    volume=10,
                    oi=1000,
                    source="upstox",
                    latency_ms=10.0,
                    record_id=f"rec_{i}_{j}"
                )
                await storage1.add_tick(tick)
            await storage1.flush()
            
        # Simulate a crash right after some un-flushed data arrives
        for j in range(5):
            tick = MarketTick(
                timestamp=time.time() * 1000,
                exchange_timestamp=time.time() * 1000,
                underlying="NIFTY",
                expiry="2026-06-25",
                strike=23000.0,
                option_type="CE",
                spot=23000.0,
                ltp=200.0,
                bid=199.0,
                ask=201.0,
                volume=10,
                oi=1000,
                source="upstox",
                latency_ms=10.0,
                record_id=f"rec_crash_{j}"
            )
            await storage1.add_tick(tick)
            
        # Crash! (storage1 is abandoned)
        del storage1
        
        # Restart
        storage2 = StorageManager()
        
        # Write some more data and flush
        for j in range(100):
            tick = MarketTick(
                timestamp=time.time() * 1000,
                exchange_timestamp=time.time() * 1000,
                underlying="NIFTY",
                expiry="2026-06-25",
                strike=23000.0,
                option_type="CE",
                spot=23000.0,
                ltp=300.0,
                bid=299.0,
                ask=301.0,
                volume=10,
                oi=1000,
                source="upstox",
                latency_ms=10.0,
                record_id=f"rec_restart_{j}"
            )
            await storage2.add_tick(tick)
        await storage2.flush()
        
        # Verification
        # Read all parquet files
        total_rows = 0
        parquet_files = list(test_raw.glob("**/*.parquet"))
        assert len(parquet_files) > 0, "No parquet files found!"
        
        for p in parquet_files:
            try:
                df = pl.read_parquet(p)
                total_rows += len(df)
            except Exception as e:
                pytest.fail(f"Parquet file corruption detected: {p} - {e}")
                
        # Total expected rows: 1200 + 100 (from restart) = 1300
        # The 5 un-flushed rows are lost due to crash, which is acceptable (1300 / 1305 = ~0.38% loss)
        expected_total = 1305
        loss_pct = ((expected_total - total_rows) / expected_total) * 100
        
        assert loss_pct < 0.5, f"Missing rows exceeded 0.5%: {loss_pct}% loss"
        assert total_rows == 1300
        
    finally:
        # Restore
        market.storage.RAW_DIR = original_raw
        market.storage.EVENTS_DIR = original_events
