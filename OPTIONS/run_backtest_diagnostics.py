"""
Targeted Backtest Diagnostics for Today's Parquet Ticks (2026-08-04)
Inspects candidates emitted by Strategy A, B, C, and D across all 1.94M ticks.
"""
import glob
import os
import sys
import time
from datetime import datetime, date
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from runner import run_pipeline, is_executable, build_trade_idea
from market.macro_sentiment import fetch_macro_data, invalidate_cache

DATE_STR = "2026-08-04"
RAW_DIR = f"data/raw/{DATE_STR}"

def run_diagnostics():
    files = sorted(glob.glob(f"{RAW_DIR}/*.parquet"))
    if not files:
        print(f"No parquet files found in {RAW_DIR}")
        return

    print(f"Loading {len(files)} parquet files for {DATE_STR}...")
    dfs = [pl.read_parquet(f) for f in files]
    full_df = pl.concat(dfs, how="diagonal_relaxed")
    
    max_ts = full_df["timestamp"].max()
    if max_ts < 1e11:
        full_df = full_df.with_columns((pl.col("timestamp") * 1000).cast(pl.Int64).alias("ts_ms"))
    else:
        full_df = full_df.with_columns((pl.col("timestamp") / 1000).cast(pl.Int64).alias("ts_ms") if max_ts > 1e13 else pl.col("timestamp").cast(pl.Int64).alias("ts_ms"))
        
    full_df = full_df.sort("ts_ms")
    
    min_ts = full_df["ts_ms"].min()
    max_ts = full_df["ts_ms"].max()
    
    # Pre-fetch macro data
    try:
        macro_data = fetch_macro_data()
    except Exception:
        macro_data = {}

    import runner
    runner.macro_cached_data = macro_data

    candidates_log = []
    
    # Replay in 5-minute steps for fast 5x execution
    ROLLING_WINDOW_MS = 15 * 60 * 1000
    current_window_start = min_ts
    step_ms = 300_000
    
    while current_window_start <= max_ts:
        window_end = current_window_start + step_ms
        context_start = max(min_ts, window_end - ROLLING_WINDOW_MS)
        
        df_chunk = full_df.filter(
            (pl.col("ts_ms") >= context_start) & (pl.col("ts_ms") < window_end)
        )
        
        if df_chunk.height > 20:
            gen_dt = datetime.fromtimestamp(window_end / 1000.0)
            try:
                df_conf, elapsed, regime = run_pipeline(df_chunk, date_str=DATE_STR, dry_run=True)
                if df_conf is not None and not df_conf.is_empty() and "confidence" in df_conf.columns:
                    for row in df_conf.iter_rows(named=True):
                        row["gen_time"] = gen_dt.strftime("%H:%M:%S")
                        row["regime_detected"] = regime
                        candidates_log.append(row)
            except Exception as e:
                pass
                
        current_window_start += step_ms

    print("\n" + "=" * 80)
    print(f"=== BACKTEST DIAGNOSTIC REPORT FOR {DATE_STR} ===")
    print("=" * 80)
    print(f"Total Ticks Evaluated: {full_df.height:,}")
    print(f"Total Raw Candidates Emitted Across 4 Engines: {len(candidates_log)}")
    print("-" * 80)
    
    if candidates_log:
        by_engine = {}
        for c in candidates_log:
            eng = c.get("_engine", "Unknown")
            by_engine[eng] = by_engine.get(eng, 0) + 1
            
        print("Candidate Distribution by Strategy Engine:")
        for eng, count in by_engine.items():
            print(f"  • {eng}: {count} candidates")
            
        print("-" * 80)
        print("Sample High-Conviction Candidates (Conf >= 0.70):")
        high_conf = [c for c in candidates_log if c.get("confidence", 0) >= 0.70]
        print(f"Total High-Conviction Candidates (Conf >= 0.70): {len(high_conf)}")
        for c in high_conf[:15]:
            print(f"  [{c.get('gen_time')}] {c.get('underlying')} {c.get('strike')} {c.get('option_type')} | Conf: {c.get('confidence',0):.4f} | Action: {c.get('action')} | Engine: {c.get('_engine')}")
    else:
        print("No raw candidates emitted.")
    print("=" * 80)

if __name__ == "__main__":
    run_diagnostics()
