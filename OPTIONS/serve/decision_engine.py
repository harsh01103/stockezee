import uuid
import time
import polars as pl
from serve.ttl import assign_ttl

def generate_decisions(df_trades: pl.DataFrame) -> pl.DataFrame:
    """
    Step 1: Decision Generation
    Converts trades into executable decisions with IDs and latencies.
    """
    if df_trades.is_empty():
        return df_trades
        
    df = df_trades.clone()
    
    # 1. Assign unique Signal IDs
    df = df.with_columns([
        pl.concat_str([
            pl.col("timestamp").cast(pl.Utf8),
            pl.col("underlying"),
            pl.col("strike").cast(pl.Utf8),
            pl.col("option_type")
        ]).hash().cast(pl.Utf8).alias("signal_id")
    ])
    
    # 2. Generated At 
    df = df.with_columns(pl.col("timestamp").alias("generated_at"))
    
    # 3. Simulate latency
    df = df.with_columns([
        (pl.lit(500) + (pl.col("signal_id").hash() % 600)).cast(pl.Int32).alias("publish_latency_ms")
    ])
    
    # 4. Entry zone 
    df = df.with_columns(pl.col("entry_price").cast(pl.Utf8).alias("entry_zone"))
    
    # 5. NO_TRADE routing
    df = df.with_columns([
        pl.when(pl.col("signal_id").hash() % 100 < 15)
        .then(pl.lit("TRADE"))
        .otherwise(pl.lit("NO_TRADE"))
        .alias("action")
    ])
    
    # 6. Assign TTL
    df = assign_ttl(df)
    
    # Keep required fields
    required = [
        "signal_id", "generated_at", "action", "underlying", "expiry", "strike", "option_type",
        "entry_zone", "stop_price", "target_price", "confidence", "publish_latency_ms", "ttl_seconds"
    ]
    
    if "stop_price" in df.columns:
        df = df.rename({"stop_price": "stop"})
    if "target_price" in df.columns:
        df = df.rename({"target_price": "target"})
        
    available = [c for c in required if c in df.columns]
    
    return df.select(available)
