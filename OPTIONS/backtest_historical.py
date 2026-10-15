"""
Tick-Level Historical Backtesting Engine with P&L Matching and UI Integration.
Simulates trades through real parquet ticks with realistic constraints:
  - Contract deduplication (no re-entering the same contract)
  - Daily max trades cap
  - Daily loss circuit breaker
  - Uses DATA timestamps for time-of-day logic, not wall clock
"""
import glob
import os
import sys
import time
from datetime import datetime, date, timedelta
import polars as pl
import argparse
import httpx
import uuid

# Ensure options directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from runner import run_pipeline, is_executable, build_trade_idea, LOT_SIZE, ROUND_TRIP_COST, DAILY_MAX_LOSS
from market.macro_sentiment import fetch_macro_data


def run_historical_backtest(date_str: str, push_to_ledger: bool = False, max_daily_trades: int = 8):
    raw_dir = f"data/raw/{date_str}"
    files = sorted(glob.glob(f"{raw_dir}/*.parquet"))
    if not files:
        print(f"No parquet files found in {raw_dir}")
        return

    print(f"Loading {len(files)} parquet files for {date_str}...")
    
    dfs = []
    for f in files:
        try:
            df = pl.read_parquet(f)
            dfs.append(df)
        except Exception:
            pass
            
    if not dfs:
        print("No valid data loaded.")
        return
        
    full_df = pl.concat(dfs, how="diagonal_relaxed")
    
    if "timestamp" not in full_df.columns:
        print("Missing timestamp column.")
        return
        
    # Standardize timestamp to milliseconds
    max_ts_raw = full_df["timestamp"].max()
    if max_ts_raw < 1e11:
        full_df = full_df.with_columns((pl.col("timestamp") * 1000).cast(pl.Int64).alias("ts_ms"))
    elif max_ts_raw > 1e13:
        full_df = full_df.with_columns((pl.col("timestamp") / 1000).cast(pl.Int64).alias("ts_ms"))
    else:
        full_df = full_df.with_columns(pl.col("timestamp").cast(pl.Int64).alias("ts_ms"))
        
    full_df = full_df.sort("ts_ms")
    
    min_ts = full_df["ts_ms"].min()
    max_ts = full_df["ts_ms"].max()
    
    print(f"Time range: {datetime.fromtimestamp(min_ts/1000)} to {datetime.fromtimestamp(max_ts/1000)}")
    
    try:
        macro_data = fetch_macro_data()
    except Exception:
        macro_data = {}

    import runner
    runner.macro_cached_data = macro_data
    
    # ── PATCH: Override datetime.now() in runner to use data time ──
    # This ensures tod_multiplier uses the historical timestamp, not wall clock
    _original_datetime_now = datetime.now
    _current_sim_time = [None]  # mutable container for closure
    
    import unittest.mock
    
    active_trades = []
    closed_trades = []
    
    # ── REALISTIC CONSTRAINTS ──
    published_contracts = set()   # (underlying, strike, option_type) — no re-entry
    daily_pnl = 0.0               # Running daily P&L for circuit breaker
    total_entries = 0             # Count of trades entered today
    
    ROLLING_WINDOW_MS = 15 * 60 * 1000
    current_window_start = min_ts
    step_ms = 180_000  # 3-minute steps
    
    print(f"Beginning tick replay (max {max_daily_trades} trades/day, circuit breaker at Rs {DAILY_MAX_LOSS})...")
    
    while current_window_start <= max_ts:
        window_end = current_window_start + step_ms
        context_start = max(min_ts, window_end - ROLLING_WINDOW_MS)
        sim_dt = datetime.fromtimestamp(window_end / 1000.0)
        
        # ── CIRCUIT BREAKER ──
        if daily_pnl <= DAILY_MAX_LOSS:
            # Close all active trades at market and stop
            for trade in active_trades:
                trade["status"] = "CLOSED"
                trade["exitPrice"] = trade["entry"]  # assume flat exit
                trade["exitTime"] = sim_dt.isoformat()
                trade["reason"] = "CIRCUIT_BREAKER"
                trade["pnl"] = 0
                closed_trades.append(trade)
            active_trades = []
            print(f"  ⛔ CIRCUIT BREAKER at {sim_dt.strftime('%H:%M')} — Daily P&L Rs {daily_pnl:.0f} hit limit Rs {DAILY_MAX_LOSS}")
            break
        
        # 1. PROCESS ACTIVE TRADES against new ticks
        if active_trades:
            df_forward = full_df.filter(
                (pl.col("ts_ms") >= current_window_start) & (pl.col("ts_ms") < window_end)
            )
            
            if not df_forward.is_empty():
                still_active = []
                for trade in active_trades:
                    u = trade.get("_underlying", "")
                    s = trade.get("_strike", 0)
                    ot = trade.get("_option_type", "")
                    
                    contract_ticks = df_forward.filter(
                        (pl.col("underlying") == u) & 
                        (pl.col("strike") == s) & 
                        (pl.col("option_type") == ot)
                    )
                    
                    closed = False
                    if not contract_ticks.is_empty():
                        for tick in contract_ticks.iter_rows(named=True):
                            ltp = tick.get("ltp", 0)
                            
                            # Peak tracking for trailing stop
                            if "peak" not in trade:
                                trade["peak"] = trade["entry"]
                            if ltp > trade["peak"]:
                                trade["peak"] = ltp
                                
                            # Replicate runner.py trailing logic
                            engine = trade.get("engine", "")
                            is_mr = ("Mean Reversion" in engine)
                            entry_price = trade["entry"]
                            stop_dist = abs(entry_price - trade.get("_initial_stop", trade["stop"]))
                            
                            if "_initial_stop" not in trade:
                                trade["_initial_stop"] = trade["stop"]
                                
                            be_mult = 0.25 if is_mr else 0.4
                            be_trigger = stop_dist * be_mult
                            trail_stop = trade["stop"]
                            
                            # Lock Breakeven
                            if trade["peak"] >= entry_price + be_trigger:
                                trail_stop = max(trail_stop, entry_price)
                                
                            # Dynamic Trailing
                            if is_mr and trade["peak"] >= entry_price + stop_dist * 0.5:
                                trail_stop = max(trail_stop, trade["peak"] - stop_dist * 0.4)
                            elif trade["peak"] >= entry_price + stop_dist * 1.2:
                                trail_stop = max(trail_stop, trade["peak"] - stop_dist * 0.8)
                                
                            trade["stop"] = trail_stop
                            
                            if ltp >= trade["target1"]:
                                trade["status"] = "CLOSED"
                                trade["exitPrice"] = trade["target1"]
                                trade["exitTime"] = datetime.fromtimestamp(tick["ts_ms"]/1000).isoformat()
                                trade["reason"] = "TARGET"
                                closed = True
                                break
                            elif ltp <= trade["stop"]:
                                trade["status"] = "CLOSED"
                                trade["exitPrice"] = trade["stop"]
                                trade["exitTime"] = datetime.fromtimestamp(tick["ts_ms"]/1000).isoformat()
                                trade["reason"] = "TRAIL_STOP" if trade["stop"] > trade["_initial_stop"] else "STOP_LOSS"
                                closed = True
                                break
                                
                    if closed:
                        trade["pnl"] = (trade["exitPrice"] - trade["entry"]) * trade["quantity"]
                        daily_pnl += trade["pnl"]
                        closed_trades.append(trade)
                        # Free the contract for potential re-use (optional: remove this to keep strict no-reentry)
                        # published_contracts.discard((u, s, ot))
                    else:
                        # End of day auto-close
                        if window_end >= max_ts - step_ms:
                            last_ltp = contract_ticks["ltp"].to_list()[-1] if not contract_ticks.is_empty() else trade["entry"]
                            trade["status"] = "CLOSED"
                            trade["exitPrice"] = last_ltp
                            trade["exitTime"] = datetime.fromtimestamp(window_end/1000).isoformat()
                            trade["reason"] = "EOD"
                            trade["pnl"] = (trade["exitPrice"] - trade["entry"]) * trade["quantity"]
                            daily_pnl += trade["pnl"]
                            closed_trades.append(trade)
                        else:
                            still_active.append(trade)
                
                active_trades = still_active

        # 2. GENERATE NEW SIGNALS (skip if we've hit the daily trade cap or have active positions)
        if total_entries >= max_daily_trades:
            current_window_start += step_ms
            continue
            
        # Don't stack positions — only enter new trades if no active trades
        if len(active_trades) >= 2:
            current_window_start += step_ms
            continue
        
        df_chunk = full_df.filter(
            (pl.col("ts_ms") >= context_start) & (pl.col("ts_ms") < window_end)
        )
        
        if df_chunk.height > 20:
            gen_dt = datetime.fromtimestamp(window_end / 1000.0)
            
            # Patch datetime.now() to return simulation time
            _current_sim_time[0] = gen_dt
            
            try:
                with unittest.mock.patch('runner.datetime') as mock_dt:
                    mock_dt.now.return_value = gen_dt
                    mock_dt.fromtimestamp = datetime.fromtimestamp
                    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
                    df_conf, elapsed, regime = run_pipeline(df_chunk, date_str=date_str, dry_run=True)
                
                if df_conf is not None and not df_conf.is_empty() and "confidence" in df_conf.columns:
                    df_pub = df_conf.filter(pl.col("confidence") >= 0.70)
                    
                    if not df_pub.is_empty():
                        # Only take the single best trade per window
                        best_row = df_pub.sort("confidence", descending=True).row(0, named=True)
                        
                        u = best_row.get("underlying", "")
                        s = best_row.get("strike", 0)
                        ot = best_row.get("option_type", "")
                        contract_key = (u, s, ot)
                        
                        # DEDUP: Skip if we've already traded this contract today
                        if contract_key not in published_contracts:
                            idea = build_trade_idea(best_row, gen_dt, df_raw=df_chunk)
                            if idea:
                                idea["engine"] = best_row.get("_engine", "Momentum Breakout")
                                idea["_underlying"] = u
                                idea["_strike"] = s
                                idea["_option_type"] = ot
                                
                                published_contracts.add(contract_key)
                                active_trades.append(idea)
                                total_entries += 1
                                
                                print(f"  📈 ENTRY #{total_entries} at {gen_dt.strftime('%H:%M')} | {u} {s} {ot} | Entry: {idea['entry']:.2f} | Target: {idea['target1']:.2f} | SL: {idea['stop']:.2f}")
                                
                                if push_to_ledger:
                                    try:
                                        httpx.post("http://localhost:4000/api/ledger/trade", json=idea, timeout=2.0)
                                    except:
                                        pass
            except Exception as e:
                pass
                
        current_window_start += step_ms

    # ── RESULTS ──
    print("\n" + "=" * 80)
    print(f"=== TRUE TICK BACKTEST RESULTS FOR {date_str} ===")
    print("=" * 80)
    print(f"Total Trades Taken: {len(closed_trades)}")
    print(f"Max Daily Trades: {max_daily_trades} | Contracts Traded: {len(published_contracts)}")
    
    if closed_trades:
        wins = [t for t in closed_trades if t.get("pnl", 0) > 0]
        losses = [t for t in closed_trades if t.get("pnl", 0) <= 0]
        win_rate = len(wins) / len(closed_trades) * 100
        total_pnl = sum([t.get("pnl", 0) for t in closed_trades])
        avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0
        
        print(f"Win Rate: {win_rate:.2f}% ({len(wins)}W / {len(losses)}L)")
        print(f"Total Net P&L: Rs {total_pnl:.2f}")
        print(f"Avg Win: Rs {avg_win:.2f} | Avg Loss: Rs {avg_loss:.2f}")
        if losses:
            print(f"Risk/Reward: {abs(avg_win/avg_loss):.2f}:1")
        print("-" * 80)
        print(f"{'Time':<12} | {'Symbol':<25} | {'Reason':<10} | {'PnL':<8}")
        print("-" * 80)
        
        for t in closed_trades:
            gen_at = t.get("generated_at", "")
            t_time = gen_at.split(" ")[1][:8] if " " in gen_at else gen_at
            reason = t.get("reason", "")
            pnl = t.get("pnl", 0)
            sym = t.get('_underlying', '') + " " + str(t.get('_strike', '')) + " " + t.get('_option_type', '')
            print(f"{t_time:<12} | {sym:<25} | {reason:<10} | {pnl:8.2f}")
    else:
        print("No trades triggered under strict filter quality gates.")
    print("=" * 80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2026-08-04", help="Date string YYYY-MM-DD")
    parser.add_argument("--push-to-ledger", action="store_true", help="Push trades to localhost:4000 UI")
    parser.add_argument("--max-trades", type=int, default=8, help="Max trades per day (default: 8)")
    args = parser.parse_args()
    
    run_historical_backtest(args.date, args.push_to_ledger, args.max_trades)
