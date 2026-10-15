import glob
import os
import polars as pl
import numpy as np
from datetime import datetime

from features.builder import process_features
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy
from signals.score import build_composite_score
from opportunities.universe import build_universe

def main():
    date_str = "2026-06-18"
    raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
    
    dfs = []
    for f in raw_files:
        _df = pl.read_parquet(f)
        _df = _df.with_columns(pl.lit(os.path.basename(f)).alias("source_file"))
        dfs.append(_df)
        
    df_raw = pl.concat(dfs, how="diagonal_relaxed")
    df_raw = df_raw.with_columns(pl.Series("row_id", range(df_raw.height)))
    
    res = process_features(df_raw, date_str, dry_run=False)
    df_feat = res["df_features"]
    
    df_res = compute_oi_flow(df_feat)
    df_res = compute_vwoim(df_res)
    df_res = compute_regime_features(df_res)
    df_res = compute_gex_proxy(df_res)
    
    df_sig = build_composite_score(df_res)
    
    df_all = df_sig.clone()
    df_all = df_all.with_columns([
        (1.0 / (1.0 + (-pl.col("composite_alpha_score") / 20.0).exp())).alias("conf_abs"),
        (pl.col("composite_alpha_score").rank("average", descending=False).over("timestamp") / pl.count("composite_alpha_score").over("timestamp")).fill_null(0.5).alias("conf_rel")
    ])
    df_all = df_all.with_columns(
        (pl.col("conf_abs") * pl.col("conf_rel").sqrt()).clip(0, 1).alias("theo_conf")
    )
    
    df_univ = build_universe(df_sig)
    
    kept_keys = df_univ.select(["timestamp", "underlying", "expiry", "strike", "option_type"]).with_columns(pl.lit(True).alias("kept"))
    df_all = df_all.join(kept_keys, on=["timestamp", "underlying", "expiry", "strike", "option_type"], how="left")
    df_all = df_all.with_columns(pl.col("kept").fill_null(False))
    df_removed = df_all.filter(pl.col("kept") == False)
    
    df_removed = df_removed.join(
        df_raw.select(["timestamp", "underlying", "expiry", "strike", "option_type", "bid", "ask", "volume"]),
        on=["timestamp", "underlying", "expiry", "strike", "option_type"],
        how="left"
    )
    
    # Filter to removed > live_max
    df_removed = df_removed.filter(pl.col("theo_conf") > 0.6608)
    
    # Top 30
    df_top = df_removed.sort("theo_conf", descending=True).head(30)
    
    if df_top.height == 0:
        print("removed_candidates: 0")
        print("executable_removed: 0")
        print("best_executable_conf: 0.0")
        print("best_executable_snapshot: None")
        print("top_failure_reason: NONE")
        print("decision: UNIVERSE_CORRECT")
        print("STOP")
        return
        
    df_top = df_top.with_columns([
        pl.when(pl.col("bid") > 0).then((pl.col("ask") - pl.col("bid")) / pl.col("bid")).otherwise(1.0).alias("spread_pct")
    ])
    
    # Calculate minutes to expiry roughly
    # Expiry format usually "2026-06-25"
    # Convert string to ms roughly
    # For this script we will assume it's positive unless we see weird data
    def get_class(row):
        bid = row.get("bid", 0) or 0
        ask = row.get("ask", 0) or 0
        vol = row.get("volume", 0) or 0
        spread = row.get("spread_pct", 1.0) or 1.0
        
        if bid <= 0 or ask <= 0:
            return "MISSING_MARKET"
        if vol == 0 or spread > 0.01:
            return "ILLIQUID"
        return "EXECUTABLE" # or FILTER_ONLY if we add filter logic
        
    dicts = df_top.to_dicts()
    results = []
    
    executable_count = 0
    best_exec_conf = 0.0
    best_exec_snap = "None"
    
    reasons = {"EXECUTABLE": 0, "ILLIQUID": 0, "EXPIRED": 0, "MISSING_MARKET": 0, "FILTER_ONLY": 0}
    
    for row in dicts:
        cls = get_class(row)
        reasons[cls] += 1
        if cls == "EXECUTABLE":
            executable_count += 1
            if row["theo_conf"] > best_exec_conf:
                best_exec_conf = row["theo_conf"]
                best_exec_snap = str({
                    "confidence": row["theo_conf"],
                    "expiry": row["expiry"],
                    "bid": row["bid"],
                    "ask": row["ask"],
                    "spread_pct": row["spread_pct"],
                    "volume": row["volume"]
                })
                
    # Top failure reason excluding executable
    fail_reasons = {k: v for k, v in reasons.items() if k != "EXECUTABLE"}
    top_fail = max(fail_reasons, key=fail_reasons.get) if any(fail_reasons.values()) else "NONE"
    
    print(f"removed_candidates: {len(dicts)}")
    print(f"executable_removed: {executable_count}")
    print(f"best_executable_conf: {best_exec_conf:.4f}")
    print(f"best_executable_snapshot: {best_exec_snap}")
    print(f"top_failure_reason: {top_fail}")
    
    if executable_count > 0:
        print("Decision: UNIVERSE_OVERBLOCKING")
    else:
        print("Decision: UNIVERSE_CORRECT")
    print("STOP")

if __name__ == "__main__":
    main()
