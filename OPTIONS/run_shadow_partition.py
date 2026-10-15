import glob
import os
import polars as pl
import numpy as np

from features.builder import process_features
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy

from opportunities.scorer import score_opportunities
from opportunities.universe import build_universe
from opportunities.ranker import rank_opportunities
from opportunities.confidence import calculate_confidence

def build_composite_shadow(df: pl.DataFrame, pk: list) -> pl.DataFrame:
    if df.is_empty():
        return df
        
    def zscore(col: str):
        return (pl.col(col) - pl.col(col).rolling_mean(window_size=20).over(pk)) / \
               (pl.col(col).rolling_std(window_size=20).over(pk) + 1e-8)
               
    features = []
    if "vwoim_smoothed" in df.columns:
        df = df.with_columns(zscore("vwoim_smoothed").fill_null(0).alias("z_vwoim"))
        features.append("z_vwoim")
        
    if "oi_flow_score" in df.columns:
        df = df.with_columns(zscore("oi_flow_score").fill_null(0).alias("z_oi_flow"))
        features.append("z_oi_flow")
        
    if "gex_proxy" in df.columns:
        df = df.with_columns(zscore("gex_proxy").fill_null(0).alias("z_gex"))
        features.append("z_gex")
        
    if not features:
        return df.with_columns(pl.lit(0.0).alias("composite_alpha_score"))
        
    sum_expr = pl.sum_horizontal(features)
    df = df.with_columns(sum_expr.alias("raw_composite"))
    
    df = df.with_columns(
        (pl.col("raw_composite") * 20.0).clip(lower_bound=-100.0, upper_bound=100.0).alias("composite_alpha_score")
    )
    
    df = df.drop(features + ["raw_composite"])
    return df

def run_pipeline(df_res: pl.DataFrame, pk: list) -> pl.DataFrame:
    # 1. Score
    df_sig = build_composite_shadow(df_res, pk)
    
    # 2. Sequential processing for ranking and confidence
    timestamps = df_sig.select("timestamp").unique().to_series().to_list()
    timestamps = sorted(timestamps)
    
    all_candidates = []
    
    for ts in timestamps:
        df_ts = df_sig.filter(pl.col("timestamp") == ts)
        
        # Universe
        df_univ = build_universe(df_ts)
        
        # Scorer
        df_opp = score_opportunities(df_univ)
        
        # Ranker
        df_opp = rank_opportunities(df_opp)
        
        # Confidence
        df_opp = calculate_confidence(df_opp)
        
        all_candidates.append(df_opp)
        
    if all_candidates:
        return pl.concat(all_candidates, how="vertical_relaxed")
    return pl.DataFrame()

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
    
    # Sort for valid rolling windows
    df_res = df_res.sort("timestamp")
    
    # Run pipelines
    pk_A = ["underlying", "expiry", "strike", "option_type"]
    pk_B = ["underlying", "expiry"]
    
    df_A = run_pipeline(df_res, pk_A)
    df_B = run_pipeline(df_res, pk_B)
    
    if df_A.height == 0 or df_B.height == 0:
        print("Empty results.")
        return
        
    # Metrics
    A_p95 = df_A["confidence"].quantile(0.95)
    B_p95 = df_B["confidence"].quantile(0.95)
    
    A_pub = df_A.filter(pl.col("confidence") > 0.75).height
    B_pub = df_B.filter(pl.col("confidence") > 0.75).height
    
    # Sort by confidence to get top 100
    top100_A = df_A.sort("confidence", descending=True).head(100)
    top100_B = df_B.sort("confidence", descending=True).head(100)
    
    vol_A = top100_A["volume"].mean()
    vol_B = top100_B["volume"].mean()
    
    confidence_lift = B_p95 - A_p95
    liquidity_delta = vol_B / vol_A if vol_A and vol_A > 0 else 0
    
    # Overlap
    # Create unique id: timestamp + underlying + expiry + strike + option_type
    def get_ids(df):
        return set(
            df.select(
                pl.concat_str([
                    pl.col("timestamp").cast(pl.Utf8),
                    pl.col("underlying"),
                    pl.col("expiry").cast(pl.Utf8),
                    pl.col("strike").cast(pl.Utf8),
                    pl.col("option_type")
                ], separator="_").alias("uid")
            )["uid"].to_list()
        )
        
    ids_A = get_ids(top100_A)
    ids_B = get_ids(top100_B)
    overlap = len(ids_A.intersection(ids_B)) / 100.0 if len(ids_A) > 0 else 0
    
    decision = ""
    if confidence_lift > 0 and liquidity_delta >= 0.8:
        decision = "PARTITION_UPGRADE"
    elif confidence_lift > 0 and liquidity_delta < 0.8:
        decision = "FALSE_UNLOCK"
    else:
        decision = "KEEP_CURRENT"
        
    print("\nOUTPUT:")
    print(f"schemeA_p95: {A_p95:.4f}")
    print(f"schemeB_p95: {B_p95:.4f}")
    print(f"schemeA_publishable: {A_pub}")
    print(f"schemeB_publishable: {B_pub}")
    print(f"decision: {decision}")
    print("STOP")

if __name__ == "__main__":
    main()
