import polars as pl
import numpy as np

def rank_features(df: pl.DataFrame, target_col: str = "future_move_pct_15m") -> dict:
    """
    Computes feature ranking metrics: IC, Rank IC, Mutual Information proxy, and Feature Stability.
    Returns a dictionary mapping feature name to its metrics.
    """
    if df.is_empty() or target_col not in df.columns:
        return {}
        
    # Drop rows where target is null
    valid_df = df.drop_nulls(subset=[target_col])
    if valid_df.height < 2:
        return {}
        
    features = [
        c for c in valid_df.columns 
        if c not in ["timestamp", "datetime", "source_file", "session_slot", "underlying", "expiry", "option_type", "strike"]
        and not c.startswith("future_")
    ]
    
    results = {}
    
    # Calculate stability by splitting into 2 halves (or more)
    # Using simple 2-half split for stability (proportion of positive correlation consistency)
    half_size = valid_df.height // 2
    df_h1 = valid_df.head(half_size)
    df_h2 = valid_df.tail(half_size)
    
    for f in features:
        # Some columns might still have nulls, fill them for correlation
        if valid_df[f].null_count() == valid_df.height:
            continue
            
        try:
            ic = valid_df.select(pl.corr(f, target_col, method="pearson")).item()
            rank_ic = valid_df.select(pl.corr(f, target_col, method="spearman")).item()
            
            # stability proxy: do the two halves agree in sign?
            ic_h1 = df_h1.select(pl.corr(f, target_col, method="pearson")).item()
            ic_h2 = df_h2.select(pl.corr(f, target_col, method="pearson")).item()
            
            # Simple stability: 1.0 if both halves have same sign and > 0.01 magnitude, else 0.5 or 0
            stability = 0.0
            if ic_h1 is not None and ic_h2 is not None:
                if np.sign(ic_h1) == np.sign(ic_h2):
                    stability = 1.0
                else:
                    stability = 0.0
            
            # MI proxy (just magnitude of rank_ic for now to avoid heavy dependencies)
            mi_proxy = abs(rank_ic) if rank_ic is not None else 0.0
            
            results[f] = {
                "information_coefficient": float(ic) if ic is not None else 0.0,
                "rank_ic": float(rank_ic) if rank_ic is not None else 0.0,
                "mutual_information": float(mi_proxy),
                "feature_stability": float(stability)
            }
        except Exception:
            pass
            
    return results
