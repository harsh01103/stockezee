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
    
    all_evals = []
    
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
        
        all_evals.append(df_eval)
        
    if not all_evals:
        print("candidates: 0")
        print("best_confidence: 0.0")
        print("share_above_070: 0.0%")
        print("share_above_075: 0.0%")
        print("decision: FEATURE_REVIEW")
        print("STOP")
        return
        
    df_all = pl.concat(all_evals)
    total_cands = df_all.height
    best_conf = df_all["confidence"].max()
    
    cnt_60 = df_all.filter(pl.col("confidence") >= 0.60).height
    cnt_65 = df_all.filter(pl.col("confidence") >= 0.65).height
    cnt_70 = df_all.filter(pl.col("confidence") >= 0.70).height
    cnt_75 = df_all.filter(pl.col("confidence") >= 0.75).height
    
    share_60 = cnt_60 / total_cands
    share_65 = cnt_65 / total_cands
    share_70 = cnt_70 / total_cands
    share_75 = cnt_75 / total_cands
    
    # Bucket [0.00-0.40]
    b1 = df_all.filter(pl.col("confidence") <= 0.40).height
    b2 = df_all.filter((pl.col("confidence") > 0.40) & (pl.col("confidence") <= 0.50)).height
    b3 = df_all.filter((pl.col("confidence") > 0.50) & (pl.col("confidence") <= 0.60)).height
    b4 = df_all.filter((pl.col("confidence") > 0.60) & (pl.col("confidence") <= 0.70)).height
    b5 = df_all.filter((pl.col("confidence") > 0.70) & (pl.col("confidence") <= 0.75)).height
    b6 = df_all.filter(pl.col("confidence") > 0.75).height
    
    print("\nOUTPUT:")
    print(f"candidates: {total_cands}")
    print(f"best_confidence: {best_conf:.4f}")
    print(f"share_above_070: {share_70*100:.2f}%")
    print(f"share_above_075: {share_75*100:.2f}%")
    
    if share_70 > 0.05:
        print("decision: WAIT_FOR_MARKET")
    elif share_65 > 0.01:
        print("decision: FEATURE_OK_LOW_ENERGY")
    else:
        print("decision: FEATURE_REVIEW")
        
    print("STOP")

if __name__ == "__main__":
    main()
