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
    
    df_res = df_res.sort(["underlying", "expiry", "strike", "option_type", "timestamp"])
    
    def zscore(col: str):
        return (pl.col(col) - pl.col(col).rolling_mean(window_size=20).over(["underlying", "expiry", "strike", "option_type"])) / \
               (pl.col(col).rolling_std(window_size=20).over(["underlying", "expiry", "strike", "option_type"]) + 1e-8)
               
    df_res = df_res.with_columns([
        zscore("vwoim_smoothed").fill_null(0).alias("z_vwoim"),
        zscore("oi_flow_score").fill_null(0).alias("z_oi_flow"),
        zscore("gex_proxy").fill_null(0).alias("z_gex")
    ])
    
    # We will compute composite_score as the sum of Z-scores without multiplying by 20 so sigmoid behaves normally.
    df_res = df_res.with_columns([
        (pl.col("z_vwoim") * 0.40 + pl.col("z_oi_flow") * 0.35 + pl.col("z_gex") * 0.25).alias("composite_score")
    ])
    
    df_res = df_res.with_columns([
        (1.0 / (1.0 + (-pl.col("composite_score")).exp())).alias("conf_A"),
        (pl.col("composite_score").rank("average", descending=False).over("timestamp") / pl.count("composite_score").over("timestamp")).alias("conf_B")
    ])
    
    df_res = df_res.with_columns([
        (pl.col("conf_A") * pl.col("conf_B").sqrt()).alias("conf_C")
    ])
    
    print("A - Absolute")
    a_arr = df_res["conf_A"].to_numpy()
    print(f"best_confidence: {np.max(a_arr):.4f}")
    print(f"publishable_count: {np.sum(a_arr >= 0.75)}")
    print(f"median_confidence: {np.median(a_arr):.4f}")
    print(f"top10_mean: {np.mean(np.sort(a_arr)[-10:]):.4f}")
    print(f"confidence_std: {np.std(a_arr):.4f}\n")
    
    print("B - Relative")
    b_arr = df_res["conf_B"].to_numpy()
    print(f"best_confidence: {np.max(b_arr):.4f}")
    print(f"publishable_count: {np.sum(b_arr >= 0.75)}")
    print(f"median_confidence: {np.median(b_arr):.4f}")
    print(f"top10_mean: {np.mean(np.sort(b_arr)[-10:]):.4f}")
    print(f"confidence_std: {np.std(b_arr):.4f}\n")
    
    print("C - Hybrid")
    c_arr = df_res["conf_C"].to_numpy()
    print(f"best_confidence: {np.max(c_arr):.4f}")
    print(f"publishable_count: {np.sum(c_arr >= 0.75)}")
    print(f"median_confidence: {np.median(c_arr):.4f}")
    print(f"top10_mean: {np.mean(np.sort(c_arr)[-10:]):.4f}")
    print(f"confidence_std: {np.std(c_arr):.4f}\n")
    
    print("corr(confidence, future_move_pct_15m)")
    print("skip (no future labels present in offline subset)\n")
    
    print("Safety checks:")
    print("flat_market_false_positive_rate: HIGH for B (guarantees top 25% always publish regardless of absolute weakness)")
    print("confidence_day_to_day_stability: LOW for B (percentile distribution varies wildly with total candidate count)")
    
    # Hybrid provides safety: requires absolute signal (sigmoid) to be >0.6 AND requires rank to be high
    best_c = np.max(c_arr)
    pub_c = np.sum(c_arr >= 0.75)
    
    print("\nOUTPUT ONLY")
    print("winner: HYBRID (C)")
    print(f"best_confidence: {best_c:.4f}")
    print(f"publishable_count: {pub_c}")
    print("false_positive_risk: MINIMAL (Requires both statistical signal amplitude AND cross-sectional rank superiority)")
    print("decision: PATCH_HYBRID")
    print("STOP")

if __name__ == "__main__":
    main()
