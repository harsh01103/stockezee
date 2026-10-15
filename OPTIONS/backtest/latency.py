import polars as pl
import numpy as np

def apply_human_latency(df: pl.DataFrame) -> pl.DataFrame:
    """
    Simulates human delays in executing the trade.
    - decision_view_delay: Uniform(1-5 sec)
    - order_submission_delay: Uniform(1-4 sec)
    - exchange_delay: Uniform(100-500 ms)
    """
    if df.is_empty():
        return df
        
    n = df.height
    np.random.seed(42) # Deterministic for audit
    
    view_delay = np.random.uniform(1.0, 5.0, n)
    sub_delay = np.random.uniform(1.0, 4.0, n)
    exc_delay = np.random.uniform(0.1, 0.5, n)
    
    total_delay = view_delay + sub_delay + exc_delay
    
    df = df.with_columns([
        pl.Series("view_delay", view_delay),
        pl.Series("sub_delay", sub_delay),
        pl.Series("exc_delay", exc_delay),
        pl.Series("total_delay_s", total_delay),
    ])
    
    # We pretend timestamp is in milliseconds, and we add total_delay_s
    # In our dataset, `timestamp` is just an integer (e.g. 1620000000000 for milliseconds)
    # We will compute `fill_ts` based on delay
    df = df.with_columns([
        (pl.col("generated_at") + (pl.col("total_delay_s") * 1000).cast(pl.Int64)).alias("fill_ts")
    ])
    
    return df
