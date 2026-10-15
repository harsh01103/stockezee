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
    
    # Compute z-scores manually
    pk = ["underlying", "expiry", "strike", "option_type"]
    def zscore(col: str):
        return (pl.col(col) - pl.col(col).rolling_mean(window_size=20).over(pk)) / \
               (pl.col(col).rolling_std(window_size=20).over(pk) + 1e-8)
               
    if "vwoim_smoothed" in df_res.columns:
        df_res = df_res.with_columns(zscore("vwoim_smoothed").fill_null(0).alias("z_vwoim"))
    if "oi_flow_score" in df_res.columns:
        df_res = df_res.with_columns(zscore("oi_flow_score").fill_null(0).alias("z_oi_flow"))
    if "gex_proxy" in df_res.columns:
        df_res = df_res.with_columns(zscore("gex_proxy").fill_null(0).alias("z_gex"))
        
    features = ["z_vwoim", "z_oi_flow", "z_gex"]
    for feat in features:
        if feat not in df_res.columns:
            df_res = df_res.with_columns(pl.lit(0.0).alias(feat))
            
    df_res = df_res.with_columns(
        (0.40 * pl.col("z_vwoim") + 0.35 * pl.col("z_oi_flow") + 0.25 * pl.col("z_gex")).alias("raw_composite")
    )
    
    df_res = df_res.drop_nulls(subset=["raw_composite"])
    
    if df_res.height == 0:
        print("feature_energy: NONE")
        print("raw_composite_p95: 0.0")
        print("estimated_conf_p95: 0.5")
        print("decision: FEATURE_TOO_WEAK")
        print("STOP")
        return
        
    rc_mean = df_res["raw_composite"].mean()
    rc_std = df_res["raw_composite"].std()
    rc_p95 = df_res["raw_composite"].quantile(0.95)
    rc_p99 = df_res["raw_composite"].quantile(0.99)
    
    conf_array = sigmoid(df_res["raw_composite"].to_numpy())
    conf_p95 = np.percentile(conf_array, 95)
    
    share_60 = np.sum(conf_array > 0.60) / len(conf_array)
    share_70 = np.sum(conf_array > 0.70) / len(conf_array)
    share_80 = np.sum(conf_array > 0.80) / len(conf_array)
    
    decision = ""
    if rc_p95 < 1:
        decision = "FEATURE_TOO_WEAK"
        feat_en = "LOW"
    elif rc_p95 >= 1 and conf_p95 < 0.70:
        decision = "NORMALIZATION_TOO_CONSERVATIVE"
        feat_en = "MODERATE"
    elif share_70 > 0.01:
        decision = "SIGNAL_EXISTS_WAIT"
        feat_en = "HIGH"
    else:
        decision = "FEATURE_TOO_WEAK"
        feat_en = "LOW"
        
    print("\nOUTPUT:")
    print(f"feature_energy: {feat_en}")
    print(f"raw_composite_p95: {rc_p95:.4f}")
    print(f"estimated_conf_p95: {conf_p95:.4f}")
    print(f"decision: {decision}")
    print("STOP")

if __name__ == "__main__":
    main()
