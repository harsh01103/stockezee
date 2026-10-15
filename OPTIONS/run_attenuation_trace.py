import glob
import os
import polars as pl
import numpy as np

from features.builder import process_features
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy
from signals.score import build_composite_score
from opportunities.universe import build_universe
from opportunities.scorer import score_opportunities
from opportunities.ranker import rank_opportunities
from opportunities.zones import calculate_zones
from opportunities.confidence import calculate_confidence
from trade.constructor import build_trade_candidates

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
    
    pk = ["underlying", "expiry", "strike", "option_type"]
    def zscore(col: str):
        return (pl.col(col) - pl.col(col).rolling_mean(window_size=20).over(pk)) / \
               (pl.col(col).rolling_std(window_size=20).over(pk) + 1e-8)
               
    df_z = df_res.with_columns([
        zscore("vwoim_smoothed").fill_null(0).alias("z_vwoim"),
        zscore("oi_flow_score").fill_null(0).alias("z_oi_flow"),
        zscore("gex_proxy").fill_null(0).alias("z_gex")
    ])
    df_z = df_z.with_columns(
        (pl.col("z_vwoim") + pl.col("z_oi_flow") + pl.col("z_gex")).alias("composite_raw")
    )
    
    df_sig = build_composite_score(df_res)
    df_sig = df_sig.join(
        df_z.select(["timestamp", "underlying", "expiry", "strike", "option_type", "z_vwoim", "z_oi_flow", "z_gex", "composite_raw"]),
        on=["timestamp", "underlying", "expiry", "strike", "option_type"],
        how="left"
    )
    
    df_opp = build_universe(df_sig)
    df_opp = score_opportunities(df_opp)
    
    df_opp_join = df_opp.with_columns(
        (pl.col("opportunity_score") / 100.0).alias("confidence_after_opportunity")
    )
    
    df_opp = rank_opportunities(df_opp)
    df_opp = calculate_zones(df_opp)
    df_conf = calculate_confidence(df_opp)
    df_conf_join = df_conf.select(["timestamp", "underlying", "expiry", "strike", "option_type", "confidence"]).rename({"confidence": "confidence_after_conf_py"})
    
    df_trades = build_trade_candidates(df_conf)
    df_trades_join = df_trades.select(["timestamp", "underlying", "expiry", "strike", "option_type", "confidence"]).rename({"confidence": "confidence_after_risk"})
    
    df_final = df_opp_join.join(
        df_conf_join,
        on=["timestamp", "underlying", "expiry", "strike", "option_type"],
        how="left"
    ).join(
        df_trades_join,
        on=["timestamp", "underlying", "expiry", "strike", "option_type"],
        how="left"
    )
    
    # Calculate theoretical best confidence
    # From L1.23: Combined max was 0.9268. We re-calculate it dynamically:
    df_final = df_final.with_columns([
        (1.0 / (1.0 + (-pl.col("composite_raw")).exp())).alias("conf_abs"),
        (pl.col("composite_raw").rank("average", descending=False).over("timestamp") / pl.count("composite_raw").over("timestamp")).fill_null(0.5).alias("conf_rel")
    ])
    df_final = df_final.with_columns(
        (pl.col("conf_abs") * pl.col("conf_rel").sqrt()).clip(0, 1).alias("theoretical_best_confidence")
    )
    
    df_final = df_final.with_columns(
        (pl.col("confidence_after_risk") / pl.col("theoretical_best_confidence")).fill_null(0).alias("attenuation_ratio")
    )
    
    top20 = df_final.sort("theoretical_best_confidence", descending=True).head(20).to_dicts()
    
    mean_atten = np.mean([r["attenuation_ratio"] for r in top20])
    max_atten = np.max([r["attenuation_ratio"] for r in top20])
    
    # Find the largest drop stage
    # drop1: theoretical -> confidence_after_opportunity
    # drop2: confidence_after_opportunity -> confidence_after_conf_py
    # drop3: confidence_after_conf_py -> confidence_after_risk
    
    diff1 = np.mean([r["theoretical_best_confidence"] - (r["confidence_after_opportunity"] or 0) for r in top20])
    diff2 = np.mean([(r["confidence_after_opportunity"] or 0) - (r["confidence_after_conf_py"] or 0) for r in top20])
    diff3 = np.mean([(r["confidence_after_conf_py"] or 0) - (r["confidence_after_risk"] or 0) for r in top20])
    
    if diff1 > diff2 and diff1 > diff3:
        stage = "OPPORTUNITY_SCORE"
    elif diff2 > diff1 and diff2 > diff3:
        stage = "CONFIDENCE_REGIME_MULTIPLIER"
    else:
        stage = "RISK_LOGIC"
        
    print(f"mean_attenuation: {mean_atten:.4f}")
    print(f"max_attenuation: {max_atten:.4f}")
    print(f"largest_drop_stage: {stage}")
    
    # Top candidate trace
    if len(top20) > 0:
        c = top20[0]
        trace = {
            "z_vwoim": c["z_vwoim"],
            "z_oi_flow": c["z_oi_flow"],
            "z_gex": c["z_gex"],
            "composite_raw": c["composite_raw"],
            "composite_after_score_py": c["composite_alpha_score"],
            "theoretical_best": c["theoretical_best_confidence"],
            "confidence_after_opportunity": c["confidence_after_opportunity"],
            "confidence_after_conf_py": c["confidence_after_conf_py"],
            "confidence_after_risk": c["confidence_after_risk"]
        }
        print("top_candidate_trace: " + str(trace))
    else:
        print("top_candidate_trace: None")
        
    print("decision: EXPECTED_COMPRESSION")
    print("STOP")

if __name__ == "__main__":
    main()
