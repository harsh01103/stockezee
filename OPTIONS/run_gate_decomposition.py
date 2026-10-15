import glob
import os
import time
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
    df_opp = calculate_confidence(df_opp)
    
    df_trades = build_trade_candidates(df_opp)
    
    df_trades = df_trades.join(
        df_opp.select(["underlying", "expiry", "strike", "option_type", "timestamp", "ask", "bid", "ltp"]),
        on=["underlying", "expiry", "strike", "option_type", "timestamp"],
        how="left"
    )
    
    df_eval = df_trades.with_columns([
        (pl.col("confidence").fill_null(0.0)),
        (pl.col("time_exit").cast(pl.Float64, strict=False).fill_null(300) * 60).alias("ttl_seconds"),
        ((pl.col("ask").cast(pl.Float64, strict=False) - pl.col("bid").cast(pl.Float64, strict=False)) / pl.col("bid").cast(pl.Float64, strict=False)).alias("spread_pct"),
        pl.lit(0.0).alias("freshness_seconds") # Assume 0.0 offline
    ])
    
    rows_in = df_eval.height
    
    # Gates
    df_conf = df_eval.filter(pl.col("confidence") >= 0.75)
    rows_after_conf = df_conf.height
    
    df_ttl = df_conf.filter(pl.col("ttl_seconds") >= 120)
    rows_after_ttl = df_ttl.height
    
    df_spread = df_ttl.filter(pl.col("spread_pct") <= 0.01)
    rows_after_spread = df_spread.height
    
    df_rr = df_spread.filter(pl.col("expected_rr") >= 1.8)
    rows_after_rr = df_rr.height
    
    df_fresh = df_rr.filter(pl.col("freshness_seconds") <= 5.0)
    rows_after_freshness = df_fresh.height
    
    conf_arr = df_eval["confidence"].to_numpy()
    max_c = np.max(conf_arr) if len(conf_arr) > 0 else 0
    p95_c = np.percentile(conf_arr, 95) if len(conf_arr) > 0 else 0
    
    print(f"max_confidence: {max_c:.4f}")
    print(f"p95_confidence: {p95_c:.4f}")
    print("best_candidate_snapshot: " + (str(df_eval.sort("confidence", descending=True).head(1).to_dicts()[0]) if rows_in > 0 else "None"))
    
    print("\nOUTPUT:")
    print(f"rows_in: {rows_in}")
    print(f"rows_after_conf: {rows_after_conf}")
    print(f"rows_after_ttl: {rows_after_ttl}")
    print(f"rows_after_spread: {rows_after_spread}")
    print(f"rows_after_rr: {rows_after_rr}")
    print(f"rows_after_freshness: {rows_after_freshness}")
    
    top_blocker = "CONFIDENCE" if rows_after_conf == 0 else ("TTL" if rows_after_ttl == 0 else ("SPREAD" if rows_after_spread == 0 else ("RR" if rows_after_rr == 0 else ("FRESHNESS" if rows_after_freshness == 0 else "NONE"))))
    
    print(f"\ntop_blocker: {top_blocker}")
    if top_blocker == "CONFIDENCE":
        print("decision: NO_SIGNAL_ENVIRONMENT")
    elif top_blocker == "NONE":
        print("decision: READY_FOR_PAPER")
    else:
        print("decision: FILTER_TOO_STRICT")
    print("STOP")

if __name__ == "__main__":
    main()
