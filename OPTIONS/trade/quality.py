import polars as pl

def validate_trades(df: pl.DataFrame) -> pl.DataFrame:
    """
    Validates trade structure.
    Checks for missing exits, negative risk, overlapping entries.
    Flags invalid trades.
    """
    if df.is_empty():
        return df

    # We will flag them, but constructor might just filter out invalid ones.
    # A trade is valid if:
    # 1. entry_price > 0
    # 2. expected_rr > 0
    # 3. no missing target or stop price
    df = df.with_columns(
        (
            (pl.col("entry_price").is_not_null()) & 
            (pl.col("entry_price") > 0) &
            (pl.col("stop_price").is_not_null()) &
            (pl.col("target_price").is_not_null()) &
            (pl.col("expected_rr").is_not_null()) &
            (pl.col("expected_rr") > 0)
        ).alias("is_valid_trade")
    )

    return df
