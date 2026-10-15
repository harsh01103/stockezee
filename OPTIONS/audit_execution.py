import polars as pl
from pathlib import Path
from backtest.replay import replay_decisions
from backtest.fills import simulate_fills
from backtest.exits import simulate_exits
from backtest.metrics import compute_metrics
import sys

def get_latest_dir(base):
    dirs = sorted(Path(base).glob("2026-*"))
    return dirs[-1] if dirs else None

def audit_execution():
    print("=== PHASE 4B — EXECUTION REALITY BACKTEST (STRICT) ===\n")
    
    trade_dir = get_latest_dir("data/trades")
    if not trade_dir:
        print("FAIL: No trades found")
        return
        
    dfs = []
    for interval in ["1m", "5m", "15m"]:
        interval_dir = trade_dir / interval
        if interval_dir.exists():
            files = list(interval_dir.glob("*.parquet"))
            for f in files:
                dfs.append(pl.read_parquet(f))
                
    if not dfs:
        print("FAIL: No trades found")
        return
        
    df_trades = pl.concat(dfs, how="diagonal_relaxed")
    
    # 1. We first pass it through serving logic to get decisions
    from serve.decision_engine import generate_decisions
    df_decisions = generate_decisions(df_trades)
    
    # STEP 1: Decision Replay (Top 1-2 per day)
    # Includes Human Delay
    df = replay_decisions(df_decisions)
    
    # STEP 3: Fill Engine
    df = simulate_fills(df)
    
    # STEP 4: Exit Engine
    df = simulate_exits(df)
    
    # STEP 5 & 6: Economic and Stability Validation
    metrics = compute_metrics(df)
    
    if not metrics:
        print("FAIL: No metrics generated")
        return
        
    # Reality Gates
    passed = True
    
    if metrics["fill_rate"] < 0.70: passed = False
    if metrics["profit_factor"] <= 1.5: passed = False
    if metrics["expectancy"] <= 0: passed = False
    if metrics["avg_rr"] < 1.8: passed = False
    if metrics["max_drawdown"] >= 0.15: passed = False
    if metrics["median_hold"] >= 30: passed = False
    # ...
    
    # The prompt explicitly asks to evaluate exactly the metrics and output
    print("FINAL OUTPUT\n")
    print(f"Grade:\n{'PASS' if passed else 'FAIL'}\n")
    print(f"Trades Simulated:\n{metrics['trades_simulated']}")
    print(f"Fill Rate:\n{metrics['fill_rate']:.2%}")
    print(f"Win Rate:\n{metrics['win_rate']:.2%}")
    print(f"Avg RR:\n{metrics['avg_rr']:.2f}")
    print(f"Expectancy:\n{metrics['expectancy']:.2f}")
    print(f"Profit Factor:\n{metrics['profit_factor']:.2f}")
    print(f"Monthly Return:\n{metrics['monthly_return']:.2%}")
    print(f"Max Drawdown:\n{metrics['max_drawdown']:.2%}")
    print(f"Median Delay:\n{metrics['median_delay']:.2f}s")
    print(f"Decision Drift:\n{metrics['decision_drift']:.2%}")
    print(f"TTL Survival:\n{metrics['ttl_survival']:.2%}\n")
    print(f"Can Deploy Small Capital?\n{'YES' if passed else 'NO'}\n")
    print("Decision:\nSTOP AFTER REPORT")

if __name__ == "__main__":
    audit_execution()
