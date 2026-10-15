import polars as pl

def assign_ttl(df: pl.DataFrame) -> pl.DataFrame:
    """
    Assigns Time-To-Live (TTL) for human executability window.
    Default is 60 seconds. High confidence trades can live longer.
    """
    if df.is_empty():
        return df
        
    df = df.with_columns([
        pl.when(pl.col("confidence") > 0.8)
        .then(pl.lit(120))
        .otherwise(pl.lit(60))
        .alias("ttl_seconds")
    ])
    
    return df
