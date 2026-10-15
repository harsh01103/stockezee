import polars as pl
import numpy as np

def validate_vwoim(df: pl.DataFrame, target_col: str = "future_move_pct_15m") -> dict:
    """
    Measures VWOIM predictive power.
    """
    if df.is_empty() or "vwoim_smoothed" not in df.columns or target_col not in df.columns:
        return {}
        
    valid_df = df.drop_nulls(subset=["vwoim_smoothed", target_col])
    if valid_df.height < 10:
        return {}
        
    try:
        corr = valid_df.select(pl.corr("vwoim_smoothed", target_col, method="pearson")).item()
        
        # Bucketing into quintiles or deciles (if enough data)
        # Using 5 buckets for small datasets
        valid_df = valid_df.with_columns(
            pl.col("vwoim_smoothed").qcut(5, labels=["1", "2", "3", "4", "5"], allow_duplicates=True).alias("bucket")
        )
        
        bucket_returns = valid_df.group_by("bucket").agg(
            pl.col(target_col).mean().alias("mean_ret")
        ).sort("bucket")
        
        rets = bucket_returns["mean_ret"].to_list()
        
        # Monotonicity check
        monotonicity = 0.0
        if len(rets) > 1:
            diffs = [rets[i] - rets[i-1] for i in range(1, len(rets))]
            pos_diffs = sum(1 for d in diffs if d > 0)
            neg_diffs = sum(1 for d in diffs if d < 0)
            monotonicity = abs(pos_diffs - neg_diffs) / len(diffs)
            
        vwoim_score = abs(corr) * (1.0 + monotonicity) if corr is not None else 0.0
        
        return {
            "vwoim_correlation": float(corr) if corr is not None else 0.0,
            "decile_monotonicity": float(monotonicity),
            "vwoim_score": float(vwoim_score)
        }
    except Exception:
        return {}
