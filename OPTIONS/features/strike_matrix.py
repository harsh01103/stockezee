import polars as pl

def build_strike_matrix(df: pl.DataFrame) -> pl.DataFrame:
    """
    Compute atm_distance and moneyness.
    Instead of filtering ATM +/- 7, we just compute for all available.
    """
    if df.is_empty():
        return df
        
    if "strike" not in df.columns or "spot" not in df.columns:
        return df.with_columns(
            pl.lit(0).alias("atm_distance"),
            pl.lit(0.0).alias("moneyness")
        )

    # For each row, the ATM strike is the strike closest to the spot
    # But since we have spot in each row, atm_distance = strike - spot
    df = df.with_columns(
        (pl.col("strike") - pl.col("spot")).alias("atm_distance"),
        (pl.col("spot") / pl.col("strike")).fill_nan(1.0).alias("moneyness")
    )
    
    return df
