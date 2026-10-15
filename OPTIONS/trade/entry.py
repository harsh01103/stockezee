import polars as pl

def apply_entry_logic(df: pl.DataFrame) -> pl.DataFrame:
    """
    Determines entry conditions.
    Defaults to MARKET at ask price, falling back to ltp if ask is 0 or null.
    """
    if df.is_empty():
        return df

    # We assume opportunities have already been generated and contain 'ask' and 'ltp'
    df = df.with_columns(
        pl.lit("MARKET").alias("entry_rule")
    )
    
    if "ask" in df.columns and "ltp" in df.columns:
        df = df.with_columns(
            pl.when(pl.col("ask") > 0)
            .then(pl.col("ask"))
            .otherwise(pl.col("ltp"))
            .alias("entry_price")
        )
    else:
        df = df.with_columns(pl.col("ltp").alias("entry_price"))

    return df
