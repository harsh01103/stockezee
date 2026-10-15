import polars as pl

def apply_exit_logic(df: pl.DataFrame) -> pl.DataFrame:
    """
    Determines stop, target, and time exits.
    Stop = -10% of entry
    Target = +20% of entry
    Time = 15:15
    """
    if df.is_empty():
        return df

    df = df.with_columns([
        pl.lit("FIXED_PCT").alias("stop_rule"),
        pl.lit("FIXED_PCT").alias("target_rule"),
        pl.lit("15:15").alias("time_exit"),
        
        # Calculate exit prices based on entry_price
        (pl.col("entry_price") * 0.90).alias("stop_price"),
        (pl.col("entry_price") * 1.20).alias("target_price")
    ])

    return df
