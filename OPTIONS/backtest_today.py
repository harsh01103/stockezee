"""
Full-Day Replay Backtest on Today's Parquet Data (2026-08-04)
Evaluates Strategy A (Momentum), Strategy B (Mean Reversion),
Strategy C (Closing Auction), and Strategy D (Expiry Power Hour Gamma).
"""
import glob
import os
import sys
import time
from datetime import datetime, date, timedelta
import polars as pl
import numpy as np

# Ensure options directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from runner import run_pipeline, is_executable, build_trade_idea, LOT_SIZE, ROUND_TRIP_COST
from market.macro_sentiment import fetch_macro_data

DATE_STR = "2026-08-04"
RAW_DIR = f"data/raw/{DATE_STR}"

def run_backtest():
    files = sorted(glob.glob(f"{RAW_DIR}/*.parquet"))
    if not files:
        print(f"No parquet files found in {RAW_DIR}")
        return

    print(f"Loading {len(files)} parquet files for {DATE_STR}...")
    
    # Read files in batches to manage memory
    dfs = []
    for f in files:
        try:
            df = pl.read_parquet(f)
            dfs.append(df)
        except Exception as e:
            pass
            
    if not dfs:
        print("No valid data loaded.")
        return
        
    full_df = pl.concat(dfs, how="diagonal_relaxed")
    print(f"Loaded total {full_df.height} tick rows.")
    
    if "timestamp" not in full_df.columns:
        print("Missing timestamp column.")
        return
        
    # Standardize timestamp to milliseconds
    max_ts = full_df["timestamp"].max()
    if max_ts < 1e11:  # Seconds
        full_df = full_df.with_columns((pl.col("timestamp") * 1000).cast(pl.Int64).alias("ts_ms"))
    else:  # Milliseconds / Microseconds
        full_df = full_df.with_columns((pl.col("timestamp") / 1000).cast(pl.Int64).alias("ts_ms") if max_ts > 1e13 else pl.col("timestamp").cast(pl.Int64).alias("ts_ms"))
        
    full_df = full_df.sort("ts_ms")
    
    # Group ticks into 15-second windows for historical replay
    WINDOW_MS = 15_000
    min_ts = full_df["ts_ms"].min()
    max_ts = full_df["ts_ms"].max()
    
    print(f"Time range: {datetime.fromtimestamp(min_ts/1000)} to {datetime.fromtimestamp(max_ts/1000)}")
    
    # Pre-fetch macro data ONCE at startup to eliminate REST HTTP latency during loop
    try:
        macro_data = fetch_macro_data()
        print(f"Macro regime pre-fetched: Risk={macro_data.get('risk_level')} | Score={macro_data.get('macro_risk_score'):.2f}")
    except Exception as e:
        print(f"Macro fetch notice: {e}")
        macro_data = {}

    import runner
    runner.macro_cached_data = macro_data
        
    published_signals = []
    
    # 15-minute rolling window size for history context
    ROLLING_WINDOW_MS = 15 * 60 * 1000
    
    current_window_start = min_ts
    step_ms = 180_000  # 3-minute steps for ultra-fast backtest execution
    
    while current_window_start <= max_ts:
        window_end = current_window_start + step_ms
        context_start = max(min_ts, window_end - ROLLING_WINDOW_MS)
        
        # Get rolling history chunk
        df_chunk = full_df.filter(
            (pl.col("ts_ms") >= context_start) & (pl.col("ts_ms") < window_end)
        )
        
        if df_chunk.height > 20:
            gen_dt = datetime.fromtimestamp(window_end / 1000.0)
            hour, minute = gen_dt.hour, gen_dt.minute
            
            # Execute strategy pipeline on chunk
            try:
                df_conf, elapsed, regime = run_pipeline(df_chunk, date_str=DATE_STR, dry_run=True)
                
                if df_conf is not None and not df_conf.is_empty() and "confidence" in df_conf.columns:
                    # Filter candidates above threshold
                    df_pub = df_conf.filter(pl.col("confidence") >= 0.70)
                    
                    if not df_pub.is_empty():
                        for row in df_pub.sort("confidence", descending=True).iter_rows(named=True):
                            engine_type = row.get("_engine", "Momentum Breakout")
                            underlying = row.get("underlying", "")
                            strike = row.get("strike", 0)
                            option_type = row.get("option_type", "")
                            conf = row.get("confidence", 0)
                            
                            # Check executability during backtest
                            # Bypass live ledger cooldowns and time-of-day limits during historical backtest replay
                            idea = build_trade_idea(row, gen_dt, df_raw=df_chunk)
                            if idea:
                                idea["engine"] = engine_type
                                idea["gen_time"] = gen_dt.strftime("%H:%M:%S")
                                published_signals.append(idea)
            except Exception as e:
                pass
                
        current_window_start += step_ms

    print("\n" + "=" * 70)
    print(f"=== BACKTEST REPLAY RESULTS FOR {DATE_STR} ===")
    print("=" * 70)
    print(f"Total Parquet Ticks Evaluated: {full_df.height:,}")
    print(f"Total Trade Signals Approved: {len(published_signals)}")
    print("-" * 70)
    
    if published_signals:
        print(f"{'Time':<10} | {'Underlying':<10} | {'Strike':<8} | {'Type':<4} | {'Conf':<6} | {'Engine':<25}")
        print("-" * 70)
        for s in published_signals:
            print(f"{s.get('gen_time',''):<10} | {s.get('underlying',''):<10} | {s.get('strike',0):<8} | {s.get('option_type',''):<4} | {s.get('confidence',0):.4f} | {s.get('engine',''):<25}")
    else:
        print("No trades triggered under strict 12-filter quality gates.")
    print("=" * 70)

if __name__ == "__main__":
    run_backtest()
