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

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

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
    
    # We keep z_vwoim, z_oi_flow, z_gex, raw_score for tracing
    return df

def run_pipeline(df_res: pl.DataFrame, pk: list) -> pl.DataFrame:
    df_sig = build_composite_shadow(df_res, pk)
    
    timestamps = df_sig.select("timestamp").unique().to_series().to_list()
    timestamps = sorted(timestamps)
    
    all_candidates = []
    
    for ts in timestamps:
        df_ts = df_sig.filter(pl.col("timestamp") == ts)
        
        # Universe
        df_univ = build_universe(df_ts)
        
        # Scorer
        df_opp = score_opportunities(df_univ)
        
        # We need to trace intermediate values
        # In score_opportunities:
        # opportunity_score = sigmoid(composite_alpha_score/20.0) * sqrt(rank) * 100.0
        # Wait, score_opportunities creates `opportunity_score`.
        # Let's rebuild the intermediates manually to trace them accurately.
        
        # In score_opportunities:
        # conf_abs = sigmoid(composite_alpha_score/20.0)
        # conf_rel = rank / count
        # opportunity_score = conf_abs * sqrt(conf_rel) * 100
        
        if "composite_alpha_score" in df_opp.columns:
            df_opp = df_opp.with_columns([
                (1.0 / (1.0 + (-pl.col("composite_alpha_score") / 20.0).exp())).alias("after_sigmoid")
            ])
            # calculate expected after_rank based on opportunity_score
            if "opportunity_score" in df_opp.columns:
                df_opp = df_opp.with_columns([
                    (pl.col("opportunity_score") / 100.0).alias("after_rank")
                ])
        
        # Ranker
        df_opp = rank_opportunities(df_opp)
        
        # Confidence
        df_opp = calculate_confidence(df_opp)
        
        if "confidence" in df_opp.columns:
            df_opp = df_opp.with_columns(pl.col("confidence").alias("after_confidence"))
            
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
    
    pk_B = ["underlying", "expiry"]
    
    df_B = run_pipeline(df_res, pk_B)
    
    if df_B.height == 0:
        print("Empty results.")
        return
        
    # Get top 500 candidates
    df_top = df_B.sort("after_confidence", descending=True).head(500)
    
    raw_p95 = df_top["raw_score"].quantile(0.95)
    sig_p95 = df_top["after_sigmoid"].quantile(0.95)
    rank_p95 = df_top["after_rank"].quantile(0.95)
    conf_p95 = df_top["after_confidence"].quantile(0.95)
    
    # Calculate drops in percentage
    # raw_score -> after_sigmoid doesn't have a direct percentage drop since raw is unbound, but we can compare the others.
    # To find largest_drop_stage:
    # sigmoid limits to [0,1].
    # After sigmoid to after rank is a direct scalar (sqrt rank).
    # After rank to after confidence is a scalar (regime multiplier).
    
    drop_rank = sig_p95 - rank_p95
    drop_conf = rank_p95 - conf_p95
    
    # Assume sigmoid loss is max(0, 1.0 - sig_p95) if raw_score > 1.0 maybe?
    # largest_drop_stage based on raw confidence values.
    # Actually, let's just pick the largest difference among:
    # 1. RANK_PENALTY: sig_p95 - rank_p95
    # 2. REGIME_PENALTY: rank_p95 - conf_p95
    
    if drop_rank > drop_conf:
        largest_drop_stage = "RANK_PENALTY"
    else:
        largest_drop_stage = "REGIME_PENALTY"
        
    decision = ""
    # IF raw_score_p95 > 1.5 AND final_p95 < 0.60
    if raw_p95 > 1.5 and conf_p95 < 0.60:
        decision = "NORMALIZATION_LIMIT"
    elif raw_p95 < 1.0:
        decision = "FEATURE_LIMIT"
    elif abs(conf_p95 - sig_p95) < 0.05:
        decision = "MARKET_LIMIT"
    else:
        decision = "FEATURE_LIMIT" # Default fallback
        
    print("\nOUTPUT:")
    print(f"raw_p95: {raw_p95:.4f}")
    print(f"sigmoid_p95: {sig_p95:.4f}")
    print(f"final_p95: {conf_p95:.4f}")
    print(f"largest_drop_stage: {largest_drop_stage}")
    print(f"decision: {decision}")
    print("STOP")

if __name__ == "__main__":
    main()
