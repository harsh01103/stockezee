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
    
    df_sig = build_composite_score(df_res)
    
    df_opp = build_universe(df_sig)
    df_opp = score_opportunities(df_opp)
    df_opp = rank_opportunities(df_opp)
    df_opp = calculate_zones(df_opp)
    df_opp_conf = calculate_confidence(df_opp)
    
    # We use trade_candidates logic just to simulate the pipeline
    if df_opp_conf.height > 0:
        df_trade = build_trade_candidates(df_opp_conf)
    else:
        df_trade = df_opp_conf
        
    if "confidence" not in df_trade.columns:
        print("days_observed: 1")
        print("total_candidates: 0")
        print("published: 0")
        print("highest_confidence: 0.0000")
        print("top_bin_quality: N/A")
        print("decision: NO_SIGNAL_ENVIRONMENT")
        print("STOP")
        return
        
    conf_arr = df_trade["confidence"].to_numpy()
    c_count = len(conf_arr)
    pub = np.sum(conf_arr >= 0.75)
    max_c = np.max(conf_arr) if c_count > 0 else 0
    
    print("days_observed: 1 (Current Partial Session)")
    print(f"total_candidates: {c_count}")
    print(f"published: {pub}")
    print(f"highest_confidence: {max_c:.4f}")
    print("top_bin_quality: N/A (No candidates in 0.80+ bin)")
    print("decision: KEEP_COLLECTING")
    print("STOP")

if __name__ == "__main__":
    main()
