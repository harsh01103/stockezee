import polars as pl

FEATURE_SCHEMA = {
    "timestamp": pl.Int64,          # Unix ms
    "underlying": pl.Utf8,          # Symbol (e.g. NIFTY)
    "expiry": pl.Utf8,              # YYYY-MM-DD
    "strike": pl.Float64,           # Strike price
    "option_type": pl.Utf8,         # CE or PE
    
    "spot": pl.Float64,             # Underlying spot price
    "ltp": pl.Float64,              # Last traded price
    "bid": pl.Float64,              # Best bid
    "ask": pl.Float64,              # Best ask
    "spread": pl.Float64,           # ask - bid
    "volume": pl.Int64,             # Cumulative volume
    "oi": pl.Int64,                 # Open Interest
    
    "delta_oi": pl.Int64,           # Change in OI from previous period
    "delta_volume": pl.Int64,       # Volume traded in current period
    
    "mid_price": pl.Float64,        # (bid + ask) / 2
    
    "oi_zscore_15m": pl.Float64,    # Rolling 21-day Z-score
    "volume_zscore_15m": pl.Float64,# Rolling 21-day Z-score
    
    "atm_distance": pl.Int64,       # Strike minus ATM strike
    
    "session_slot": pl.Utf8,        # HH:MM based on timestamp
    "source_file": pl.Utf8          # Parquet file name source
}

def validate_schema(df: pl.DataFrame) -> bool:
    """Validate DataFrame matches required schema."""
    expected_cols = set(FEATURE_SCHEMA.keys())
    actual_cols = set(df.columns)
    
    if not expected_cols.issubset(actual_cols):
        missing = expected_cols - actual_cols
        raise ValueError(f"Missing required columns: {missing}")
        
    return True
