import polars as pl

def calculate_zones(df: pl.DataFrame) -> pl.DataFrame:
    """
    Step 4 & 5: Entry Zone and Exit Candidates
    entry_zone_low, entry_zone_high
    soft_target, hard_target, invalidation
    """
    if df.is_empty():
        return df
        
    if "ltp" not in df.columns:
        # Fallback if no LTP
        df = df.with_columns(pl.lit(100.0).alias("ltp"))
        
    if "spread" not in df.columns:
        df = df.with_columns(pl.lit(1.0).alias("spread"))
        
    # Example logic (research only, no actual execution engine):
    # Entry Zone: From LTP down to LTP - spread*2
    df = df.with_columns([
        (pl.col("ltp") - pl.col("spread") * 2.0).alias("entry_zone_low"),
        pl.col("ltp").alias("entry_zone_high")
    ])
    
    # We define volatility context. Let's use `volatility_regime` if available, else static
    if "volatility_regime" in df.columns:
        df = df.with_columns(pl.col("volatility_regime").alias("vol_proxy"))
    else:
        df = df.with_columns(pl.lit(0.01).alias("vol_proxy"))
        
    # Exit targets based on standard deviation of underlying (proxy mapped to option)
    # We estimate 1 std dev for soft target, 2 for hard target.
    # We assume 'vol_proxy' is a return standard deviation.
    # Approximate option move = spot * vol_proxy * delta (assume delta=0.5 ATM)
    
    if "spot" not in df.columns:
        df = df.with_columns(pl.lit(20000.0).alias("spot"))
        
    df = df.with_columns([
        (pl.col("spot") * pl.col("vol_proxy") * 0.5).fill_null(10.0).alias("expected_move")
    ])
    
    df = df.with_columns([
        (pl.col("entry_zone_high") + pl.col("expected_move")).alias("soft_target"),
        (pl.col("entry_zone_high") + pl.col("expected_move") * 2.0).alias("hard_target"),
        (pl.col("entry_zone_low") - pl.col("expected_move") * 0.5).alias("invalidation")
    ])
    
    df = df.drop(["vol_proxy", "expected_move"])
    
    return df
