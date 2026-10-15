import pytest
import time
from market.validator import MarketValidator
from market.schema import MarketTick

def test_duplicate_cache():
    validator = MarketValidator()
    
    # 1. First tick is valid
    tick1 = MarketTick(
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
        record_id="dup_test_1"
    )
    assert validator.validate(tick1) == True
    
    # 2. Exact same tick id should be duplicate
    assert validator.validate(tick1) == False
    assert validator.drop_reasons["duplicate"] == 1
    
    # 3. Cache memory bound validation
    # Add 100,000 more ticks to evict the first one
    for i in range(100_005):
        t = MarketTick(
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
            record_id=f"dup_fill_{i}"
        )
        validator.validate(t)
        
    # The original "dup_test_1" should now be evicted from cache
    # Validating it again should return True since it looks like a new unseen tick
    tick1.timestamp = time.time() * 1000 # updating timestamp to pass missing_timestamp check
    tick1.exchange_timestamp = time.time() * 1000
    assert validator.validate(tick1) == True
