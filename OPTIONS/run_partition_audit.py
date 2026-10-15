import glob
import os
import polars as pl
import numpy as np

from features.builder import process_features
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy

def main():
    date_str = "2026-06-18"
    raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
    
    dfs = []
    for f in raw_files:
        _df = pl.read_parquet(f)
        _df = _df.with_columns(pl.lit(os.path.basename(f)).alias("source_file"))
        dfs.append(_df)
        
    df_raw = pl.concat(dfs, how="diagonal_relaxed")
    
    res = process_features(df_raw, date_str, dry_run=False)
    df_feat = res["df_features"]
    
    df_res = compute_oi_flow(df_feat)
    df_res = compute_vwoim(df_res)
    df_res = compute_regime_features(df_res)
    df_res = compute_gex_proxy(df_res)
    
    # Sort by timestamp BEFORE rolling mean!
    df_res = df_res.sort("timestamp")
    
    pk = ["underlying", "expiry", "strike", "option_type"]
    
    # 1. raw_std
    # 2. rolling_std_nonnull_ratio
    # 3. zscore_nonzero_ratio
    # 4. zscore_abs_gt_0_5
    # 5. zscore_abs_gt_1
    
    rows_total = df_res.height
    
    # Partition metrics
    df_counts = df_res.group_by(pk).len()
    unique_partitions = df_counts.height
    partitions_with_20plus_rows = df_counts.filter(pl.col("len") >= 20).height
    median_rows_per_partition = df_counts["len"].median()
    max_rows_per_partition = df_counts["len"].max()
    
    def zscore(col: str):
        return (pl.col(col) - pl.col(col).rolling_mean(window_size=20).over(pk)) / \
               (pl.col(col).rolling_std(window_size=20).over(pk) + 1e-8)
               
    def roll_std(col: str):
        return pl.col(col).rolling_std(window_size=20).over(pk)
        
    if "vwoim_smoothed" in df_res.columns:
        df_res = df_res.with_columns([
            roll_std("vwoim_smoothed").alias("rstd_vwoim"),
            zscore("vwoim_smoothed").fill_null(0).alias("z_vwoim")
        ])
    if "oi_flow_score" in df_res.columns:
        df_res = df_res.with_columns([
            roll_std("oi_flow_score").alias("rstd_oi_flow"),
            zscore("oi_flow_score").fill_null(0).alias("z_oi_flow")
        ])
    if "gex_proxy" in df_res.columns:
        df_res = df_res.with_columns([
            roll_std("gex_proxy").alias("rstd_gex"),
            zscore("gex_proxy").fill_null(0).alias("z_gex")
        ])
        
    features = ["z_vwoim", "z_oi_flow", "z_gex"]
    for feat in features:
        if feat not in df_res.columns:
            df_res = df_res.with_columns(pl.lit(0.0).alias(feat))
            
    df_res = df_res.with_columns(
        (0.40 * pl.col("z_vwoim") + 0.35 * pl.col("z_oi_flow") + 0.25 * pl.col("z_gex")).alias("raw_composite")
    )
    
    # Collect rolling std nonnull ratio
    # We use vwoim_smoothed to represent the rolling std non-null ratio, 
    # since all features share the same partition window size (20).
    if "rstd_vwoim" in df_res.columns:
        rstd_nonnull_count = df_res.filter(pl.col("rstd_vwoim").is_not_null()).height
        rolling_std_nonnull_ratio = rstd_nonnull_count / rows_total if rows_total > 0 else 0
    else:
        rolling_std_nonnull_ratio = 0.0
        
    rc_non_zero = df_res.filter(pl.col("raw_composite") != 0).height
    zscore_nonzero_ratio = rc_non_zero / rows_total if rows_total > 0 else 0
    
    rc_p95 = df_res["raw_composite"].quantile(0.95)
    
    decision = ""
    if rolling_std_nonnull_ratio < 0.20:
        decision = "WINDOW_STARVATION"
    elif zscore_nonzero_ratio < 0.05:
        decision = "PARTITION_TOO_FINE"
    elif rc_p95 > 1:
        decision = "SIGNAL_EXISTS"
    else:
        decision = "FEATURE_WEAK"
        
    print("\nOUTPUT:")
    print(f"rows_total: {rows_total}")
    print(f"unique_partitions: {unique_partitions}")
    print(f"median_rows_per_partition: {median_rows_per_partition}")
    print(f"rolling_std_nonnull_ratio: {rolling_std_nonnull_ratio*100:.2f}%")
    print(f"raw_composite_p95: {rc_p95:.4f}")
    print(f"decision: {decision}")
    print("STOP")

if __name__ == "__main__":
    main()
