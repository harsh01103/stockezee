import polars as pl

def compute_vwoim(df: pl.DataFrame) -> pl.DataFrame:
    """
    Computes Volume Weighted Open Interest Momentum (VWOIM).
    Requires: volume, delta_oi, ltp
    """
    if df.is_empty():
        return df
        
    pk = ["underlying", "expiry", "strike", "option_type"]
    
    # Calculate VWAP
    # VWAP = cumulative(price * volume) / cumulative(volume)
    # Since we have `ltp` and `delta_volume`, we use delta_volume for the period
    df = df.with_columns([
        (pl.col("ltp") * pl.col("delta_volume")).cum_sum().over(pk).alias("cum_pv"),
        pl.col("delta_volume").cum_sum().over(pk).alias("cum_v")
    ])
    
    df = df.with_columns([
        (pl.col("cum_pv") / pl.col("cum_v")).fill_nan(0).fill_null(0).alias("rolling_vwap")
    ])
    
    # Direction: +1 if ltp > rolling_vwap, else -1
    df = df.with_columns([
        pl.when(pl.col("ltp") > pl.col("rolling_vwap")).then(1).otherwise(-1).alias("direction")
    ])
    
    # Calculate signed metrics
    df = df.with_columns([
        (pl.col("volume") * pl.col("direction")).alias("signed_volume"),
        (pl.col("oi") * pl.col("direction")).alias("signed_oi"),
        (pl.col("volume") * pl.col("delta_oi") * pl.col("direction")).alias("vwoim_raw")
    ])
    
    # vwoim (which is vwoim_raw)
    df = df.with_columns(pl.col("vwoim_raw").alias("vwoim"))
    
    # Smoothed VWOIM (e.g., 5-period moving average)
    df = df.with_columns([
        pl.col("vwoim_raw").rolling_mean(window_size=5).over(pk).fill_null(0).alias("vwoim_smoothed")
    ])
    
    # Clean up temp columns
    df = df.drop(["cum_pv", "cum_v", "rolling_vwap"])
    
    return df
