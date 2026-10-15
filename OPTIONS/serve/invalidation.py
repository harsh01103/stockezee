import polars as pl

def check_invalidation(df_decisions: pl.DataFrame, current_time) -> pl.DataFrame:
    """
    Simulates early invalidation checks (e.g. price moved away).
    Not heavily used in this purely read-only mock, but stubbed for completeness.
    """
    if df_decisions.is_empty():
        return df_decisions
        
    df = df_decisions.with_columns(pl.lit(False).alias("is_invalidated"))
    return df
