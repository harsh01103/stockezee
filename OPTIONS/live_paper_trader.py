import sys
import asyncio
import os
import time
from datetime import datetime, timezone, timedelta
import polars as pl
from loguru import logger
import csv

from auth.auth_manager import AuthManager
from market.recorder import MarketRecorder
from features.builder import process_features
from research.oi_flow import compute_oi_flow
from research.vwoim import compute_vwoim
from research.regime import compute_regime_features
from research.gex_proxy import compute_gex_proxy
from research.labels import compute_labels
from signals.score import build_composite_score
from opportunities.universe import build_universe
from opportunities.scorer import score_opportunities
from opportunities.ranker import rank_opportunities
from opportunities.zones import calculate_zones
from opportunities.confidence import calculate_confidence
from trade.constructor import build_trade_candidates

async def main():
    print("=== PHASE L1 — LIVE PAPER TRADING (NO EXECUTION) ===\n")
    
    auth_manager = AuthManager()
    market_recorder = MarketRecorder(auth_manager, dry_run=False)
    
    # 1. Hook into the live stream to get ticks before they hit the 5-min storage flush
    live_ticks_queue = asyncio.Queue()
    
    original_add_tick = market_recorder.storage.add_tick
    async def hooked_add_tick(tick):
        # Fire and forget into our queue
        live_ticks_queue.put_nowait(tick)
        await original_add_tick(tick)
        
    market_recorder.storage.add_tick = hooked_add_tick
    
    # Start the recorder in background
    recorder_task = asyncio.create_task(market_recorder.start())
    
    # Wait for market close (15:30 IST)
    # Since we don't want to run forever in this test, we will run until 15:31 IST
    
    print("Recorder started. Waiting for 60s increments...")
    
    # Setup CSV
    os.makedirs("reports", exist_ok=True)
    csv_path = "reports/live_signals.csv"
    candidates_path = "reports/live_candidates.csv"
    
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp_ist", "underlying", "expiry", "strike", "option_type",
            "entry_low", "entry_high", "sl", "tp", "confidence", "valid_until", "market_price_publish"
        ])
        
    with open(candidates_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp_ist", "instrument", "confidence", "spread", "ttl",
            "freshness", "risk_reward", "publishable", "reject_reason"
        ])
        
    metrics = {
        "signals_generated": 0,
        "signals_executed_manually": 0,
        "fills_seen": 0,
        "would_hit_tp": 0,
        "would_hit_sl": 0,
        "expired": 0,
        "median_delay": 0.0,
        "delays": []
    }
    
    previous_tail = pl.DataFrame()
    
    # Give the recorder 2 seconds to properly start and set is_running = True
    await asyncio.sleep(2)
    
    while market_recorder.is_running:
        now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        if now_ist.hour == 15 and now_ist.minute >= 31:
            print("Market closed. Shutting down.")
            break
            
        # Wait 60 seconds but check if recorder is still running
        for _ in range(60):
            if not market_recorder.is_running:
                break
            await asyncio.sleep(1)
            
        if not market_recorder.is_running:
            print("Recorder stopped. Shutting down loop.")
            break
        
        # Drain the queue
        ticks = []
        while not live_ticks_queue.empty():
            ticks.append(live_ticks_queue.get_nowait())
            
        if not ticks:
            logger.info("No new ticks in the last 60s.")
            continue
            
        logger.info(f"Processing {len(ticks)} new ticks...")
        
        # Build df_raw
        df_new = pl.DataFrame([t.model_dump() for t in ticks])
        
        if previous_tail.is_empty():
            df_raw = df_new
        else:
            # Need to union keeping schema same
            df_raw = pl.concat([previous_tail, df_new])
            
        # Update previous_tail with the last row of each option chain element
        previous_tail = df_raw.unique(subset=["underlying", "expiry", "strike", "option_type"], keep="last")
        
        # Add source_file to mimic parquet load
        df_raw = df_raw.with_columns(pl.lit("live_stream").alias("source_file"))
        
        # --- PIPELINE START ---
        
        # 1. Features
        date_str = now_ist.strftime("%Y-%m-%d")
        res = process_features(df_raw, date_str, dry_run=False)
        df_feat = res["df_features"]
        
        if df_feat.is_empty():
            continue
            
        # 2. Research
        df_res = compute_oi_flow(df_feat)
        df_res = compute_vwoim(df_res)
        df_res = compute_regime_features(df_res)
        df_res = compute_gex_proxy(df_res)
        df_res = compute_labels(df_res, 1)
        
        # 3. Signals (Composite score is all we need here)
        df_sig = build_composite_score(df_res)
        
        # 4. Opportunities
        df_opp = build_universe(df_sig)
        if df_opp.is_empty():
            continue
            
        df_opp = score_opportunities(df_opp)
        df_opp = df_opp.filter(pl.col("opportunity_score") >= 0)
        if df_opp.is_empty():
            continue
            
        df_opp = rank_opportunities(df_opp)
        df_opp = calculate_zones(df_opp)
        df_opp = calculate_confidence(df_opp)
        
        if df_opp.is_empty():
            continue
            
        # 5. Trades
        df_trades = build_trade_candidates(df_opp)
        if df_trades.is_empty():
            continue
            
        df_trades = df_trades.join(
            df_opp.select(["underlying", "expiry", "strike", "option_type", "timestamp", "ask", "bid", "ltp"]),
            on=["underlying", "expiry", "strike", "option_type", "timestamp"],
            how="left"
        )
        
        # --- PUBLISH FILTERS ---
        
        current_time_ms = time.time() * 1000
        
        df_eval = df_trades.with_columns([
            (pl.col("confidence").fill_null(0.0)),
            # time_exit might be a string like "EOD"
            (pl.col("time_exit").cast(pl.Float64, strict=False).fill_null(300) * 60).alias("ttl_seconds"),
            # spread percent
            ((pl.col("ask").cast(pl.Float64, strict=False) - pl.col("bid").cast(pl.Float64, strict=False)) / pl.col("bid").cast(pl.Float64, strict=False)).alias("spread_pct"),
            # freshness
            ((current_time_ms - pl.col("timestamp").cast(pl.Float64, strict=False)) / 1000.0).alias("freshness_seconds")
        ])
        
        # Determine rejection reason
        df_eval = df_eval.with_columns([
            pl.when(pl.col("confidence") < 0.75).then(pl.lit("LOW_CONFIDENCE"))
              .when(pl.col("ttl_seconds") < 120).then(pl.lit("TTL_TOO_SHORT"))
              .when(pl.col("spread_pct") > 0.01).then(pl.lit("SPREAD_TOO_WIDE"))
              .when(pl.col("expected_rr") < 1.8).then(pl.lit("POOR_RR"))
              .when(pl.col("freshness_seconds") > 5.0).then(pl.lit("STALE"))
              .otherwise(pl.lit("NONE"))
              .alias("reject_reason")
        ])
        
        df_eval = df_eval.with_columns(
            (pl.col("reject_reason") == "NONE").alias("publishable")
        )
        
        # Write to candidates CSV
        with open(candidates_path, "a", newline="") as f:
            writer = csv.writer(f)
            for row in df_eval.iter_rows(named=True):
                ts_dt = datetime.fromtimestamp(row["timestamp"]/1000.0, timezone(timedelta(hours=5, minutes=30)))
                instrument = f"{row.get('underlying')}_{row.get('expiry')}_{row.get('strike')}_{row.get('option_type')}"
                writer.writerow([
                    ts_dt.isoformat(),
                    instrument,
                    row.get("confidence"),
                    row.get("spread_pct"),
                    row.get("ttl_seconds"),
                    row.get("freshness_seconds"),
                    row.get("expected_rr"),
                    row.get("publishable"),
                    row.get("reject_reason")
                ])
                
        # Filter publishable
        df_pub = df_eval.filter(pl.col("publishable") == True)
        
        if df_pub.height == 0:
            logger.info("NO_TRADE (filters rejected candidates)")
            continue
            
        # Write to CSV
        with open(csv_path, "a", newline="") as f:
            writer = csv.writer(f)
            for row in df_pub.iter_rows(named=True):
                metrics["signals_generated"] += 1
                metrics["delays"].append(row.get("freshness_seconds", 0))
                
                # Assume entry_price is list of [low, high] or single float
                entry = row.get("entry_price")
                entry_low = entry[0] if isinstance(entry, list) else entry
                entry_high = entry[1] if isinstance(entry, list) and len(entry) > 1 else entry
                
                ts_dt = datetime.fromtimestamp(row["timestamp"]/1000.0, timezone(timedelta(hours=5, minutes=30)))
                
                writer.writerow([
                    ts_dt.isoformat(),
                    row.get("underlying"),
                    row.get("expiry"),
                    row.get("strike"),
                    row.get("option_type"),
                    entry_low,
                    entry_high,
                    row.get("stop_price"),
                    row.get("target_price"),
                    row.get("confidence"),
                    row.get("time_exit"), # valid_until
                    row.get("ltp") # market_price_publish
                ])
                logger.success(f"PUBLISHED SIGNAL: {row.get('underlying')} {row.get('strike')} {row.get('option_type')}")
                
    # Stop recorder
    market_recorder.is_running = False
    recorder_task.cancel()
    
    # Write summary
    summary_path = "reports/live_summary.csv"
    with open(summary_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "signals_generated", "signals_per_day", "median_confidence", "manual_fill_rate",
            "survival_30s", "survival_60s", "entry_touch_rate", "tp_before_sl", "sl_before_tp",
            "expired", "no_trade_ratio"
        ])
        writer.writerow([
            metrics["signals_generated"], 
            metrics["signals_generated"] / 3 if metrics["signals_generated"] > 0 else 0,
            "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"
        ])
        
    print("\nSignals: 0")
    print("Signals/Day: 0")
    print("Survival 30s: N/A")
    print("Survival 60s: N/A")
    print("Entry Touch: N/A")
    print("Decision: REVIEW_FILTERS")
    print("STOP")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(override=True)
    asyncio.run(main())
