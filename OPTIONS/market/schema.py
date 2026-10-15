from pydantic import BaseModel
from typing import Optional

class MarketTick(BaseModel):
    timestamp: float
    exchange_timestamp: float
    underlying: str
    expiry: str
    strike: float
    option_type: str  # CE or PE
    spot: float
    ltp: float
    bid: float
    ask: float
    volume: int
    oi: int
    obi: float = 0.0  # Order Book Imbalance (Level 5)
    source: str       # e.g., 'upstox'
    source_type: str = "REAL" # REAL, CACHE, MOCK
    latency_ms: float
    record_id: str
    oi_stale: bool = False
    feed_type: str = "UNKNOWN"
    missing_fields: list[str] = []
