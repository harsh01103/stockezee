import polars as pl
import numpy as np

def run_walkforward_validation(df: pl.DataFrame, target_col: str = "future_move_pct_15m") -> dict:
    """
    Simulates an expanding window walk-forward validation with purged overlap.
    """
    if df.is_empty() or target_col not in df.columns:
        return {}
        
    valid_df = df.drop_nulls(subset=[target_col])
    
    # We need a temporal sequence, sort by timestamp
    valid_df = valid_df.sort("timestamp")
    total_rows = valid_df.height
    
    if total_rows < 20:
        return {}
        
    # Split into 4 chunks for expanding window
    # Folds:
    # Train: chunk 1, Val: chunk 2 (purged overlap)
    # Train: chunk 1,2, Val: chunk 3
    # Train: chunk 1,2,3, Val: chunk 4
    
    chunk_size = total_rows // 4
    
    # We will pick a representative feature to validate out-of-sample
    rep_feature = "vwoim_smoothed" if "vwoim_smoothed" in valid_df.columns else "oi_flow_score"
    if rep_feature not in valid_df.columns:
        return {}
        
    oos_ics = []
    in_sample_ics = []
    
    # Purge gap: to prevent label leakage. For 15m labels, we need to purge 15m of data.
    # In row count terms, if data is 1m, purge is 15 rows * num instruments.
    # We'll approximate purge gap as 5% of chunk size.
    purge_gap = max(1, int(chunk_size * 0.05))
    
    try:
        for i in range(1, 4):
            train_end = i * chunk_size
            val_start = train_end + purge_gap
            val_end = (i + 1) * chunk_size
            
            if val_start >= val_end or val_end > total_rows:
                break
                
            train_df = valid_df.slice(0, train_end)
            val_df = valid_df.slice(val_start, val_end - val_start)
            
            if train_df.height > 5 and val_df.height > 5:
                train_ic = train_df.select(pl.corr(rep_feature, target_col, method="pearson")).item()
                val_ic = val_df.select(pl.corr(rep_feature, target_col, method="pearson")).item()
                
                if train_ic is not None:
                    in_sample_ics.append(float(train_ic))
                if val_ic is not None:
                    oos_ics.append(float(val_ic))
                    
        avg_oos_ic = np.mean(oos_ics) if oos_ics else 0.0
        avg_is_ic = np.mean(in_sample_ics) if in_sample_ics else 0.0
        
        drift = abs(avg_is_ic - avg_oos_ic) / (abs(avg_is_ic) + 1e-6)
        
        return {
            "avg_oos_ic": float(avg_oos_ic),
            "avg_is_ic": float(avg_is_ic),
            "train_val_drift": float(drift),
            "oos_metrics": {
                "folds_evaluated": len(oos_ics),
                "is_ics": in_sample_ics,
                "oos_ics": oos_ics
            }
        }
    except Exception:
        return {}
