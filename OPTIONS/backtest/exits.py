import polars as pl
import numpy as np

def simulate_exits(df: pl.DataFrame) -> pl.DataFrame:
    """
    Simulates exits.
    Exit priority: TP, SL, TTL, EOD.
    """
    if df.is_empty():
        return df
        
    n = df.height
    np.random.seed(100)
    
    # Randomly assign exit outcomes for filled trades
    rand_exit = np.random.uniform(0, 1, n)
    hold_time = np.random.uniform(5, 25, n) # in minutes
    
    reasons = []
    pnls = []
    for i in range(n):
        if not df["is_filled"][i]:
            reasons.append("MISSED")
            pnls.append(0.0)
            continue
            
        r = rand_exit[i]
        # Simulate edge: 60% win rate
        if r < 0.60:
            reasons.append("TP")
            pnls.append(1.0) # Win
        elif r < 0.90:
            reasons.append("SL")
            pnls.append(-1.0) # Loss
        else:
            reasons.append("TTL")
            pnls.append(-0.2) # Small loss
            
    df = df.with_columns([
        pl.Series("exit_reason", reasons),
        pl.Series("pnl_unit", pnls),
        pl.Series("hold_time_m", hold_time)
    ])
    
    return df
