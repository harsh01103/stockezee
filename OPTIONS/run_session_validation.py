import glob
import os
import polars as pl
import csv

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
    
    timestamps = df_sig.select("timestamp").unique().to_series().to_list()
    timestamps = sorted(timestamps)
    
    os.makedirs("reports", exist_ok=True)
    obs_path = "reports/session_observation.csv"
    pub_path = "reports/published_signals.csv"
    
    with open(obs_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp", "candidate_count", "max_confidence", "count_above_0_60",
            "count_above_0_75", "published_count", "top_underlying", "top_expiry",
            "top_confidence", "top_rr", "top_spread", "top_volume"
        ])
        
    with open(pub_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "instrument", "confidence"])
        
    global_max_conf = 0.0
    global_published = 0
    global_mins_above_60 = 0
    global_mins_above_75 = 0
    
    for ts in timestamps:
        df_ts = df_sig.filter(pl.col("timestamp") == ts)
        
        df_univ = build_universe(df_ts)
        if df_univ.height == 0:
            continue
            
        df_opp = score_opportunities(df_univ)
        df_opp = rank_opportunities(df_opp)
        df_opp = calculate_zones(df_opp)
        df_conf = calculate_confidence(df_opp)
        
        if df_conf.height == 0:
            continue
            
        df_trades = build_trade_candidates(df_conf)
        df_trades = df_trades.join(
            df_conf.select(["underlying", "expiry", "strike", "option_type", "timestamp", "ask", "bid", "volume"]),
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
        
        df_sorted = df_eval.sort("confidence", descending=True)
        top = df_sorted.head(1).to_dicts()[0]
        
        c = top.get("confidence", 0.0)
        max_conf = df_eval["confidence"].max()
        global_max_conf = max(global_max_conf, max_conf)
        
        count_60 = df_eval.filter(pl.col("confidence") >= 0.60).height
        count_75 = df_eval.filter(pl.col("confidence") >= 0.75).height
        published_count = df_pub.height
        
        if max_conf >= 0.60:
            global_mins_above_60 += 1
        if max_conf >= 0.75:
            global_mins_above_75 += 1
            
        global_published += published_count
        
        with open(obs_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                ts,
                df_eval.height,
                f"{max_conf:.4f}",
                count_60,
                count_75,
                published_count,
                top.get("underlying", ""),
                top.get("expiry", ""),
                f"{c:.4f}",
                f"{top.get('expected_rr', 0):.4f}",
                f"{top.get('spread_pct', 0):.4f}",
                top.get("volume", 0)
            ])
            
        if published_count > 0:
            with open(pub_path, "a", newline="") as f:
                writer = csv.writer(f)
                for row in df_pub.to_dicts():
                    writer.writerow([
                        ts,
                        f"{row.get('underlying')}_{row.get('expiry')}_{row.get('strike')}_{row.get('option_type')}",
                        row.get("confidence")
                    ])

    print("\nOUTPUT:")
    print("days_observed: 1")
    print(f"peak_confidence: {global_max_conf:.4f}")
    print(f"signals_published: {global_published}")
    
    if global_published >= 1:
        print("decision: FIRST_REAL_SIGNAL")
    elif global_max_conf >= 0.75:
        print("decision: READY_FOR_PAPER_REVIEW")
    elif global_max_conf >= 0.65:
        print("decision: CLOSE_WAIT")
    else:
        print("decision: FEATURE_REVIEW")
    print("STOP")

if __name__ == "__main__":
    main()
