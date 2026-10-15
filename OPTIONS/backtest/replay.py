import polars as pl
from backtest.latency import apply_human_latency

def replay_decisions(df_decisions: pl.DataFrame) -> pl.DataFrame:
    """
    Reconstruct historical decision stream.
    Filters to Top 1-2 opportunities per day.
    """
    if df_decisions.is_empty():
        return df_decisions
        
    df = df_decisions.filter(pl.col("action") == "TRADE")
    
    if df.is_empty():
        return df
        
    # Convert generated_at (ms) to date
    df = df.with_columns([
        pl.from_epoch(pl.col("generated_at"), time_unit="ms").dt.date().alias("date")
    ])
    
    # Sort by confidence descending
    df = df.sort(["date", "confidence"], descending=[False, True])
    
    # Take top 2 per day
    df = df.group_by("date").head(2)
    
    # Apply latencies
    df = apply_human_latency(df)
    
    return df
