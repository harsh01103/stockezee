import polars as pl
from loguru import logger

def normalize_tod(df: pl.DataFrame) -> pl.DataFrame:
    """
    Implements Time-of-Day (TOD) normalization for volume and OI.
    Calculates median and IQR per session_slot over the available window.
    Applies Z-score transformation and clips at ±10.
    """
    if "session_slot" not in df.columns:
        logger.warning("session_slot not found in DataFrame, skipping TOD normalization")
        return df

    epsilon = 1e-9

    # Calculate median and IQR per session_slot and underlying+strike+option_type (or just underlying?)
    # Usually TOD is per instrument. The prompt says "For each time slot: median, IQR. Compute OI_Z."
    # We will do it per (underlying, expiry, strike, option_type, session_slot)
    
    # Calculate group stats
    stats = df.group_by(["underlying", "expiry", "strike", "option_type", "session_slot"]).agg(
        pl.col("oi").median().alias("oi_median"),
        (pl.col("oi").quantile(0.75) - pl.col("oi").quantile(0.25)).alias("oi_iqr"),
        pl.col("volume").median().alias("vol_median"),
        (pl.col("volume").quantile(0.75) - pl.col("volume").quantile(0.25)).alias("vol_iqr")
    )
    
    df = df.join(stats, on=["underlying", "expiry", "strike", "option_type", "session_slot"], how="left")
    
    # Compute z-scores
    df = df.with_columns(
        ((pl.col("oi") - pl.col("oi_median")) / (pl.col("oi_iqr") + epsilon))
        .clip(lower_bound=-10.0, upper_bound=10.0)
        .alias("oi_zscore_15m"),
        
        ((pl.col("volume") - pl.col("vol_median")) / (pl.col("vol_iqr") + epsilon))
        .clip(lower_bound=-10.0, upper_bound=10.0)
        .alias("volume_zscore_15m")
    )
    
    df = df.drop(["oi_median", "oi_iqr", "vol_median", "vol_iqr"])
    
    return df
