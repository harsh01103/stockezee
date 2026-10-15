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
    df = df.with_columns(sum_expr.alias("raw_score"))
    
    df = df.with_columns(
        (pl.col("raw_score") * 20.0).clip(lower_bound=-100.0, upper_bound=100.0).alias("composite_alpha_score")
    )
    
    return df

def run_pipeline(df_res: pl.DataFrame, pk: list) -> pl.DataFrame:
    df_sig = build_composite_shadow(df_res, pk)
    
    timestamps = df_sig.select("timestamp").unique().to_series().to_list()
    timestamps = sorted(timestamps)
    
    all_candidates = []
    
    for ts in timestamps:
        df_ts = df_sig.filter(pl.col("timestamp") == ts)
        df_opp = calculate_confidence(rank_opportunities(score_opportunities(build_universe(df_ts))))
        if "confidence" in df_opp.columns:
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
    
    df_res = df_res.sort("timestamp")
    
    pk_A = ["underlying", "expiry", "strike", "option_type"]
    pk_B = ["underlying", "expiry"]
    
    df_A = run_pipeline(df_res, pk_A)
    df_B = run_pipeline(df_res, pk_B)
    
    if df_A.height == 0 or df_B.height == 0:
        print("Empty results.")
        return
        
    peak_A = df_A["confidence"].max()
    peak_B = df_B["confidence"].max()
    
    published_A = df_A.filter(pl.col("confidence") > 0.75).height
    published_B = df_B.filter(pl.col("confidence") > 0.75).height
    
    # Calculate liquidity delta and spread delta for top 100
    top100_A = df_A.sort("confidence", descending=True).head(100)
    top100_B = df_B.sort("confidence", descending=True).head(100)
    
    vol_A = top100_A["volume"].mean()
    vol_B = top100_B["volume"].mean()
    liquidity_delta = vol_B / vol_A if vol_A > 0 else 1.0
    
    spread_A = top100_A["spread"].mean()
    spread_B = top100_B["spread"].mean()
    spread_delta = spread_B - spread_A
    
    # Duplicate cluster rate for B
    pub_B_df = df_B.filter(pl.col("confidence") > 0.75)
    if pub_B_df.height > 0:
        clusters = pub_B_df.select(["timestamp", "underlying", "expiry"]).unique().height
        duplicate_cluster_rate = (pub_B_df.height - clusters) / pub_B_df.height
    else:
        duplicate_cluster_rate = 0.0
        
    decision = ""
    # IF published_B > published_A AND liquidity stable AND spread stable
    if published_B > published_A and liquidity_delta >= 0.8 and spread_delta <= 0.05:
        decision = "PROMOTE_B"
    elif published_B == published_A or (peak_B - peak_A) < 0.05:
        decision = "KEEP_A"
    elif duplicate_cluster_rate > 0.5:
        decision = "KEEP_A_RANKED"
    else:
        # Fallback to PROMOTE_B if B unlocks peak_confidence safely
        if peak_B > peak_A and liquidity_delta >= 0.8:
            decision = "PROMOTE_B"
        else:
            decision = "KEEP_A"
            
    # However the session might have published 0 for both.
    # If both published 0, published_B == published_A, which means KEEP_A based on the strict rules!
    # Let's evaluate exactly as the rules say.
    if published_B > published_A and liquidity_delta >= 0.8 and spread_delta <= 0.05:
        decision = "PROMOTE_B"
    elif published_B == published_A or (peak_B - peak_A) < 0.05:
        decision = "KEEP_A"
    elif duplicate_cluster_rate > 0.5:
        decision = "KEEP_A_RANKED"
    
    print("\nOUTPUT:")
    print("days: 1")
    print(f"published_A: {published_A}")
    print(f"published_B: {published_B}")
    print(f"peak_A: {peak_A:.4f}")
    print(f"peak_B: {peak_B:.4f}")
    print(f"decision: {decision}")
    print("STOP")

if __name__ == "__main__":
    main()
