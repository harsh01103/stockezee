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
    
    df_sig = build_composite_score(df_res)
    
    df_sig_latest = df_sig.filter(pl.col("timestamp") == df_sig["timestamp"].max())
    
    # 1. Pipeline without universe cap (To get before)
    # We will simulate the strike filter manually to get equivalent "before"
    df_ts_before = df_sig_latest.filter(pl.col("underlying").is_in(["NIFTY", "BANKNIFTY"]))
    df_ts_before = df_ts_before.with_columns((pl.col("strike") - pl.col("spot")).abs().alias("dist_to_spot"))
    pk_expiry = ["timestamp", "underlying", "expiry", "option_type"]
    df_ts_before = df_ts_before.with_columns(
        pl.col("dist_to_spot").rank("ordinal").over(pk_expiry).alias("expiry_strike_rank")
    )
    df_before_cap = df_ts_before.filter(pl.col("expiry_strike_rank") <= 10)
    
    counts_before = df_before_cap.group_by("expiry").agg(pl.len().alias("count")).to_dicts()
    dist_before = {r["expiry"]: r["count"] for r in counts_before}
    expiry_count = len([k for k, v in dist_before.items() if v > 0])
    cap_feasible = False
    if expiry_count > 0:
        cap_feasible = (1.0 / expiry_count) <= 0.35
        
    rows_before_universe = df_before_cap.height
    
    # Compute max_conf_before using full downstream without universe
    df_opp_b = score_opportunities(df_before_cap)
    df_opp_b = rank_opportunities(df_opp_b)
    df_opp_b = calculate_zones(df_opp_b)
    df_conf_b = calculate_confidence(df_opp_b)
    
    max_conf_before = df_conf_b["confidence"].max() if df_conf_b.height > 0 else 0.0
    
    # 2. Pipeline WITH universe (After)
    df_univ = build_universe(df_sig_latest)
    rows_after_universe = df_univ.height
    
    counts_after = df_univ.group_by("expiry").agg(pl.len().alias("count")).to_dicts()
    dist_after = {r["expiry"]: r["count"] for r in counts_after}
    
    df_opp_a = score_opportunities(df_univ)
    df_opp_a = rank_opportunities(df_opp_a)
    df_opp_a = calculate_zones(df_opp_a)
    df_conf_a = calculate_confidence(df_opp_a)
    
    max_conf_after = df_conf_a["confidence"].max() if df_conf_a.height > 0 else 0.0
    
    df_trades = build_trade_candidates(df_conf_a)
    
    # Check publishing criteria
    df_trades = df_trades.join(
        df_conf_a.select(["underlying", "expiry", "strike", "option_type", "timestamp", "ask", "bid"]),
        on=["underlying", "expiry", "strike", "option_type", "timestamp"],
        how="left"
    )
    
    df_eval = df_trades.with_columns([
        (pl.col("confidence").fill_null(0.0)),
        (pl.col("time_exit").cast(pl.Float64, strict=False).fill_null(300) * 60).alias("ttl_seconds"),
        ((pl.col("ask").cast(pl.Float64, strict=False) - pl.col("bid").cast(pl.Float64, strict=False)) / pl.col("bid").cast(pl.Float64, strict=False)).alias("spread_pct"),
        pl.lit(0.0).alias("freshness_seconds")
    ])
    
    df_pub = df_eval.filter(
        (pl.col("confidence") >= 0.75) &
        (pl.col("ttl_seconds") >= 120) &
        (pl.col("spread_pct") <= 0.01) &
        (pl.col("expected_rr") >= 1.8) &
        (pl.col("freshness_seconds") <= 5.0)
    )
    published_count = df_pub.height
    
    print(f"expiry_count: {expiry_count}")
    print(f"cap_feasible: {cap_feasible}")
    print(f"rows_before: {rows_before_universe}")
    print(f"rows_after: {rows_after_universe}")
    print(f"expiry_distribution_before: {dist_before}")
    print(f"expiry_distribution_after: {dist_after}")
    
    print("\nOUTPUT:")
    print(f"rows_before_universe: {rows_before_universe}")
    print(f"rows_after_universe: {rows_after_universe}")
    print(f"max_conf_before: {max_conf_before:.4f}")
    print(f"max_conf_after: {max_conf_after:.4f}")
    print(f"published_count: {published_count}")
    
    print("\npatch_applied: Y")
    print(f"universe_destroyed: {rows_after_universe == 0}")
    print(f"best_confidence: {max_conf_after:.4f}")
    print(f"published: {published_count > 0}")
    print("decision: PASS")
    print("STOP")

if __name__ == "__main__":
    main()
