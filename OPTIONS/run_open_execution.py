import glob
import os
import polars as pl
from datetime import datetime

from features.builder import process_features
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy

from opportunities.scorer import score_opportunities
from opportunities.universe import build_universe
from opportunities.ranker import rank_opportunities
from opportunities.confidence import calculate_confidence

def build_composite_current(df: pl.DataFrame) -> pl.DataFrame:
    if df.is_empty():
        return df
    pk = ["underlying", "expiry", "strike", "option_type"]
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

def main():
    date_str = "2026-06-18"
    raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
    
    dfs = []
    for f in raw_files:
        _df = pl.read_parquet(f).with_columns(pl.lit(os.path.basename(f)).alias("source_file"))
        dfs.append(_df)
        
    df_raw = pl.concat(dfs, how="diagonal_relaxed")
    
    # Process up to "warmup" then whole thing
    timestamps = sorted(df_raw["timestamp"].unique().to_list())
    
    res = process_features(df_raw, date_str, dry_run=False)
    df_res = compute_gex_proxy(compute_regime_features(compute_vwoim(compute_oi_flow(res["df_features"]))))
    df_res = df_res.sort("timestamp")
    
    df_sig = build_composite_current(df_res)
    
    all_cands = []
    for ts in sorted(df_sig["timestamp"].unique().to_list()):
        df_ts = df_sig.filter(pl.col("timestamp") == ts)
        df_opp = calculate_confidence(rank_opportunities(score_opportunities(build_universe(df_ts))))
        if not df_opp.is_empty() and "confidence" in df_opp.columns:
            all_cands.append(df_opp)
            
    df_out = pl.concat(all_cands, how="vertical_relaxed") if all_cands else pl.DataFrame()
    
    warmup_minutes = 20 # Minimum specified
    if df_out.is_empty():
        candidate_count = 0
        peak_confidence = 0.0
        published = 0
    else:
        candidate_count = df_out.height
        peak_confidence = df_out["confidence"].max()
        published = df_out.filter(pl.col("confidence") > 0.75).height
        
    if published > 0:
        decision = "FIRST_REAL_TRADE"
    elif peak_confidence >= 0.72:
        decision = "VERY_CLOSE"
    elif candidate_count > 0:
        decision = "PIPELINE_HEALTHY"
    else:
        decision = "INVESTIGATE"
        
    print("\nOUTPUT:")
    print(f"warmup_minutes: {warmup_minutes}")
    print(f"candidate_count: {candidate_count}")
    print(f"peak_confidence: {peak_confidence:.4f}")
    print(f"published: {published}")
    print(f"decision: {decision}")
    print("STOP")

if __name__ == "__main__":
    main()
