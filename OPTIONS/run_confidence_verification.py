import glob
import os
import polars as pl
import time
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
    
    if not raw_files:
        print("No raw files found.")
        return
        
    dfs = []
    for f in raw_files:
        _df = pl.read_parquet(f)
        _df = _df.with_columns(pl.lit(os.path.basename(f)).alias("source_file"))
        dfs.append(_df)
        
    df_raw = pl.concat(dfs, how="diagonal_relaxed")
    
    res = process_features(df_raw, date_str, dry_run=False)
    df_feat = res["df_features"]
    
    if df_feat.is_empty():
        return
        
    df_res = compute_oi_flow(df_feat)
    df_res = compute_vwoim(df_res)
    df_res = compute_regime_features(df_res)
    df_res = compute_gex_proxy(df_res)
    
    df_sig = build_composite_score(df_res)
    
    # We will compute confidence exactly as in live_paper_trader
    df_opp = build_universe(df_sig)
    if not df_opp.is_empty():
        df_opp = score_opportunities(df_opp)
        df_opp = rank_opportunities(df_opp)
        df_opp = calculate_zones(df_opp)
        df_opp_conf = calculate_confidence(df_opp)
    else:
        df_opp_conf = pl.DataFrame()
        
    df_trades = build_trade_candidates(df_opp_conf) if not df_opp_conf.is_empty() else pl.DataFrame()
    
    if not df_trades.is_empty():
        df_trades = df_trades.join(
            df_opp_conf.select(["underlying", "expiry", "strike", "option_type", "timestamp", "ask", "bid", "ltp"]),
            on=["underlying", "expiry", "strike", "option_type", "timestamp"],
            how="left"
        )
        current_time_ms = time.time() * 1000
        df_eval = df_trades.with_columns([
            (pl.col("confidence").fill_null(0.0)),
            (pl.col("time_exit").cast(pl.Float64, strict=False).fill_null(300) * 60).alias("ttl_seconds"),
            ((pl.col("ask").cast(pl.Float64, strict=False) - pl.col("bid").cast(pl.Float64, strict=False)) / pl.col("bid").cast(pl.Float64, strict=False)).alias("spread_pct"),
        ])
    else:
        df_eval = pl.DataFrame()
        
    # Now we do the requested STEP outputs
    # Pre-unlock: the first 20 minutes of timestamps
    # Post-unlock: the remaining timestamps
    timestamps = sorted(df_opp_conf["timestamp"].unique().to_list())
    
    print("STEP 1")
    for t in timestamps[-5:]:
        sub = df_opp_conf.filter(pl.col("timestamp") == t)
        print(f"minute_ts: {t}")
        print(f"candidate_count: {sub.height}")
        print(f"mean_confidence: {sub['confidence'].mean():.4f}")
        print(f"p90_confidence: {np.percentile(sub['confidence'].to_numpy(), 90):.4f}" if sub.height > 0 else "0.0")
        print(f"max_confidence: {sub['confidence'].max():.4f}\n")
        
    print("STEP 2")
    # rolling_std percent nonzero in df_sig
    # Wait, we need to manually compute standard deviations of the actual signals across the entire set to see how many were nonzero
    for col in ["z_vwoim", "z_oi_flow", "z_gex"]:
        if col in df_sig.columns:
            nz = df_sig.filter(pl.col(col) != 0).height
            print(f"rolling_std({col}) nonzero: {(nz / df_sig.height * 100):.2f}%")
            
    print("\nSTEP 3")
    if len(timestamps) > 20:
        pre_ts = timestamps[:20]
        post_ts = timestamps[20:]
        pre_df = df_opp_conf.filter(pl.col("timestamp").is_in(pre_ts))
        post_df = df_opp_conf.filter(pl.col("timestamp").is_in(post_ts))
        
        pre_conf_mean = pre_df['confidence'].mean() if not pre_df.is_empty() else 0
        post_conf_mean = post_df['confidence'].mean() if not post_df.is_empty() else 0
        
        print(f"confidence_delta: {post_conf_mean - pre_conf_mean:.4f}")
        print(f"candidate_delta: {post_df.height - pre_df.height}")
    else:
        print("confidence_delta: 0.0000")
        print("candidate_delta: 0")
        
    print("\nSTEP 4")
    if not df_eval.is_empty():
        pub = df_eval.filter(
            (pl.col("confidence") >= 0.75) &
            (pl.col("ttl_seconds") >= 120) &
            (pl.col("expected_rr") >= 1.8) &
            (pl.col("spread_pct") <= 0.01)
        )
        print("Publication readiness")
        print(f"count: {pub.height}")
    else:
        print("count: 0")
        
    print("\nSTEP 5")
    print("Output only:")
    print(f"history_rows: {df_feat.height}")
    print(f"std_unlocked: {True if len(timestamps) > 20 else False}")
    best_c = df_opp_conf['confidence'].max() if not df_opp_conf.is_empty() else 0.0
    print(f"best_confidence: {best_c:.4f}")
    print(f"publishable_count: {pub.height if not df_eval.is_empty() else 0}")
    print(f"decision: {'READY_FOR_LIVE_PAPER' if len(timestamps) > 20 else 'KEEP_RUNNING'}")
    print("STOP")

if __name__ == "__main__":
    main()
