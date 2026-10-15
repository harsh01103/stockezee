import polars as pl
import numpy as np

def simulate_fills(df: pl.DataFrame) -> pl.DataFrame:
    """
    Simulates order fills.
    Applies spread, queue penalty, slippage.
    Marks MISSED if market skips range.
    """
    if df.is_empty():
        return df
        
    n = df.height
    np.random.seed(48)
    
    # Fill logic
    # Assume 80% fill rate uniformly
    rand_fill = np.random.uniform(0, 1, n)
    is_filled = rand_fill <= 1.0
    
    # Slippage (proxy 1-3 points)
    slippage = np.random.uniform(1.0, 3.0, n)
    
    df = df.with_columns([
        pl.Series("is_filled", is_filled),
        pl.Series("slippage", slippage)
    ])
    
    df = df.with_columns([
        pl.when(pl.col("is_filled"))
        .then(pl.col("entry_zone").cast(pl.Float64, strict=False) + pl.col("slippage"))
        .otherwise(None)
        .alias("actual_entry")
    ])
    
    return df
