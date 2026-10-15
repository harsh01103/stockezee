import polars as pl

def compute_labels(df: pl.DataFrame, interval_minutes: int) -> pl.DataFrame:
    """
    Computes forward predictive labels.
    future_move_pct: Forward return of the underlying spot.
    future_option_move: Forward return of the option LTP.
    Labels generated for +15m, +30m, +60m.
    """
    if df.is_empty():
        return df
        
    pk = ["underlying", "expiry", "strike", "option_type"]
    
    # Calculate the number of shifts needed based on the current interval
    shifts = {
        "15m": max(1, 15 // interval_minutes),
        "30m": max(1, 30 // interval_minutes),
        "60m": max(1, 60 // interval_minutes)
    }
    
    df = df.sort(["underlying", "expiry", "strike", "option_type", "timestamp"])
    
    for label, shift_val in shifts.items():
        # Negative shift looks forward in time
        df = df.with_columns([
            (pl.col("spot").shift(-shift_val).over(pk) / pl.col("spot") - 1).alias(f"future_move_pct_{label}"),
            (pl.col("ltp").shift(-shift_val).over(pk) / pl.col("ltp") - 1).alias(f"future_option_move_{label}")
        ])
        
    return df
