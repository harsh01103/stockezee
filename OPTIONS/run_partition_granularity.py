import glob
import os
import polars as pl
import numpy as np

from features.builder import process_features
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def evaluate_scheme(df_res: pl.DataFrame, pk: list) -> dict:
    rows_total = df_res.height
    df_counts = df_res.group_by(pk).len()
    
    unique_partitions = df_counts.height
    median_rows = df_counts["len"].median()
    p25_rows = df_counts["len"].quantile(0.25)
    p75_rows = df_counts["len"].quantile(0.75)
    
    rows_with_20plus = df_counts.filter(pl.col("len") >= 20).height
    rows_with_50plus = df_counts.filter(pl.col("len") >= 50).height
    
    def zscore(col: str):
        return (pl.col(col) - pl.col(col).rolling_mean(window_size=20).over(pk)) / \
               (pl.col(col).rolling_std(window_size=20).over(pk) + 1e-8)
               
    def roll_std(col: str):
        return pl.col(col).rolling_std(window_size=20).over(pk)
        
    df_eval = df_res.clone()
    
    if "vwoim_smoothed" in df_eval.columns:
        df_eval = df_eval.with_columns([
            roll_std("vwoim_smoothed").alias("rstd_vwoim"),
            zscore("vwoim_smoothed").fill_null(0).alias("z_vwoim")
        ])
    if "oi_flow_score" in df_eval.columns:
        df_eval = df_eval.with_columns([
            zscore("oi_flow_score").fill_null(0).alias("z_oi_flow")
        ])
    if "gex_proxy" in df_eval.columns:
        df_eval = df_eval.with_columns([
            zscore("gex_proxy").fill_null(0).alias("z_gex")
        ])
        
    features = ["z_vwoim", "z_oi_flow", "z_gex"]
    for feat in features:
        if feat not in df_eval.columns:
            df_eval = df_eval.with_columns(pl.lit(0.0).alias(feat))
            
    df_eval = df_eval.with_columns(
        (0.40 * pl.col("z_vwoim") + 0.35 * pl.col("z_oi_flow") + 0.25 * pl.col("z_gex")).alias("raw_composite")
    )
    
    if "rstd_vwoim" in df_eval.columns:
        rstd_nonnull_count = df_eval.filter(pl.col("rstd_vwoim").is_not_null()).height
        rolling_std_nonnull_ratio = rstd_nonnull_count / rows_total if rows_total > 0 else 0
    else:
        rolling_std_nonnull_ratio = 0.0
        
    rc_p95 = df_eval["raw_composite"].quantile(0.95)
    
    conf_array = sigmoid(df_eval["raw_composite"].to_numpy())
    
    # rank("average") equivalent normalized
    n = len(conf_array)
    # estimate maximum conf: max(conf_abs) * max(sqrt_rank)
    # the maximum rank percent is 1.0 (actually slightly less due to ties, but we can assume max rank is ~1.0)
    # If there are many ties at 0.0, the average rank is 0.5.
    
    max_raw = df_eval["raw_composite"].max()
    max_conf_abs = sigmoid(max_raw) if max_raw is not None else 0.5
    
    return {
        "unique_partitions": unique_partitions,
        "median_rows": median_rows,
        "p25_rows": p25_rows,
        "p75_rows": p75_rows,
        "rows_with_20plus": rows_with_20plus,
        "rows_with_50plus": rows_with_50plus,
        "rolling_std_nonnull_ratio": rolling_std_nonnull_ratio,
        "raw_composite_p95": rc_p95,
        "estimated_max_confidence": max_conf_abs * 1.0 # sqrt(1.0) is 1.0
    }

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
    
    df_res = df_res.sort("timestamp")
    
    pk_A = ["underlying", "expiry", "strike", "option_type"]
    pk_B = ["underlying", "expiry"]
    pk_C = ["underlying"]
    
    res_A = evaluate_scheme(df_res, pk_A)
    res_B = evaluate_scheme(df_res, pk_B)
    res_C = evaluate_scheme(df_res, pk_C)
    
    ratio_A = res_A["rolling_std_nonnull_ratio"]
    ratio_B = res_B["rolling_std_nonnull_ratio"]
    ratio_C = res_C["rolling_std_nonnull_ratio"]
    
    decision = ""
    if ratio_B > (ratio_A * 3.0) and ratio_B > 0.50:
        decision = "OVERPARTITIONED"
    elif ratio_C > (ratio_B * 2.0) and ratio_C > 0.50:
        decision = "FEATURE_TOO_LOCAL"
    else:
        decision = "NEED_MORE_SESSIONS"
        
    best_conf = max(res_A["estimated_max_confidence"], res_B["estimated_max_confidence"], res_C["estimated_max_confidence"])
    
    print("\nOUTPUT:")
    print(f"scheme_A_nonnull: {ratio_A*100:.2f}%")
    print(f"scheme_B_nonnull: {ratio_B*100:.2f}%")
    print(f"scheme_C_nonnull: {ratio_C*100:.2f}%")
    print(f"estimated_best_conf: {best_conf:.4f}")
    print(f"decision: {decision}")
    print("STOP")

if __name__ == "__main__":
    main()
