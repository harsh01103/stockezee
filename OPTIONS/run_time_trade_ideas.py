"""PHASE O2N — TIME-AWARE TRADE IDEA RECONSTRUCTION"""
import glob, os, csv, polars as pl
from datetime import datetime, timedelta

date_str = "2026-06-19"

# Load trade ideas
ideas_csv = pl.read_csv("reports/final_trade_ideas.csv")

# Load raw data
raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
dfs = [pl.read_parquet(f) for f in raw_files]
df_raw = pl.concat(dfs, how="diagonal_relaxed").sort("timestamp")
df_options = df_raw.filter(
    (pl.col("strike") > 0) & (pl.col("option_type").is_in(["CE", "PE"]))
).sort("timestamp")

print("Ideas: " + str(ideas_csv.height))
print("Option ticks: " + str(df_options.height))

def ts_to_ist(ts_ms):
    """Convert epoch ms to IST string."""
    dt = datetime.fromtimestamp(ts_ms / 1000)
    return dt.strftime("%H:%M:%S")

def simulate_trail2(prices, timestamps, entry_price, stop_price, t1_price, t2_price):
    """Best performing variant: D1 trail after +2%, trail 2%."""
    if not prices:
        return None
    actual_entry = prices[0]
    entry_ts = timestamps[0]
    actual_stop = stop_price
    peak = actual_entry
    exit_price = prices[-1]
    exit_ts = timestamps[-1]
    stopped = False
    t1_hit = False
    t2_hit = False
    t1_ts = None
    mfe = 0
    mfe_ts = None
    mae = 0
    mae_ts = None
    
    for i in range(1, len(prices)):
        p = prices[i]
        ts = timestamps[i]
        
        # Track MFE/MAE
        pnl_pct = (p - actual_entry) / actual_entry * 100
        if pnl_pct > mfe:
            mfe = pnl_pct
            mfe_ts = ts
        if pnl_pct < mae:
            mae = pnl_pct
            mae_ts = ts
        
        if p > peak:
            peak = p
        
        # Trail activation
        gain = (peak - actual_entry) / actual_entry
        if gain >= 0.02:
            trail_stop = peak * 0.98
            actual_stop = max(actual_stop, trail_stop)
        
        if p <= actual_stop:
            stopped = True
            exit_price = p
            exit_ts = ts
            break
        
        if p >= t1_price and not t1_hit:
            t1_hit = True
            t1_ts = ts
        if p >= t2_price and not t2_hit:
            t2_hit = True
            exit_price = p
            exit_ts = ts
            break
    
    final_pnl = round((exit_price - actual_entry) / actual_entry * 100, 2)
    hold_min = round((exit_ts - entry_ts) / 60000, 1)
    
    if t2_hit:
        outcome = "T2_REACHED"
    elif t1_hit and not stopped:
        outcome = "T1_ONLY"
    elif stopped and final_pnl > 0:
        outcome = "TRAIL_PROFIT"
    elif stopped:
        outcome = "STOPPED"
    else:
        outcome = "OPEN"
    
    return {
        "entry_ts": entry_ts, "exit_ts": exit_ts,
        "entry_price": round(actual_entry, 2), "exit_price": round(exit_price, 2),
        "t1_hit": t1_hit, "t1_ts": t1_ts, "t2_hit": t2_hit,
        "mfe": round(mfe, 2), "mfe_ts": mfe_ts,
        "mae": round(mae, 2), "mae_ts": mae_ts,
        "hold_min": hold_min, "pnl": final_pnl, "outcome": outcome,
    }

results = []
for row_idx in range(min(ideas_csv.height, 10)):
    idea = ideas_csv.row(row_idx, named=True)
    
    underlying = idea["underlying"]
    expiry = str(idea["expiry"])
    strike = float(idea["strike"])
    option_type = idea["option_type"]
    entry_price = float(idea["entry"])
    stop_price = float(idea["stop"])
    t1_price = float(idea["target_1"])
    t2_price = float(idea["target_2"])
    
    contract = underlying + " " + str(int(strike)) + " " + option_type
    
    # Get ticks
    mask = (
        (df_options["underlying"] == underlying) &
        (df_options["expiry"] == expiry) &
        (df_options["strike"] == strike) &
        (df_options["option_type"] == option_type)
    )
    df_c = df_options.filter(mask).sort("timestamp")
    all_prices = [r for r in df_c["ltp"].to_list() if r is not None and r > 0]
    all_ts = [r for r in df_c["timestamp"].to_list() if r is not None]
    
    if not all_prices:
        continue
    
    # Use second half as forward
    mid = len(all_prices) // 2
    fwd_prices = all_prices[mid:]
    fwd_ts = all_ts[mid:]
    
    # Generation time = midpoint of data
    gen_ts = all_ts[mid]
    
    # Entry window: generation + 0-5 minutes
    entry_window_start = gen_ts
    entry_window_end = gen_ts + 5 * 60 * 1000  # 5 min
    
    # Invalid if not entered by generation + 15 minutes
    invalid_by = gen_ts + 15 * 60 * 1000
    
    # Simulate with D1 (best performer)
    sim = simulate_trail2(fwd_prices, fwd_ts, entry_price, stop_price, t1_price, t2_price)
    
    if sim is None:
        continue
    
    # Time computations
    time_to_entry = 0  # immediate
    time_to_mfe = round((sim["mfe_ts"] - sim["entry_ts"]) / 60000, 1) if sim["mfe_ts"] else 0
    time_to_mae = round((sim["mae_ts"] - sim["entry_ts"]) / 60000, 1) if sim["mae_ts"] else 0
    time_to_exit = sim["hold_min"]
    
    # Classify hold
    if sim["hold_min"] < 15:
        hold_class = "SCALP"
    elif sim["hold_min"] < 90:
        hold_class = "INTRADAY"
    else:
        hold_class = "POSITIONAL"
    
    result = {
        "rank": row_idx + 1,
        "underlying": underlying,
        "expiry": expiry,
        "strike": strike,
        "option_type": option_type,
        "direction": "BEARISH" if option_type == "PE" else "BULLISH",
        "timestamp_generated": ts_to_ist(gen_ts),
        "entry_window": ts_to_ist(entry_window_start) + " - " + ts_to_ist(entry_window_end),
        "entry": sim["entry_price"],
        "stop": stop_price,
        "target1": t1_price,
        "target2": t2_price,
        "exit_method": "TRAIL_2%",
        "time_to_mfe_min": time_to_mfe,
        "time_to_mae_min": time_to_mae,
        "mfe_pct": sim["mfe"],
        "mae_pct": sim["mae"],
        "expected_hold": sim["hold_min"],
        "hold_class": hold_class,
        "actual_pnl": sim["pnl"],
        "actual_outcome": sim["outcome"],
        "entry_time": ts_to_ist(sim["entry_ts"]),
        "exit_time": ts_to_ist(sim["exit_ts"]),
        "best_time": ts_to_ist(sim["mfe_ts"]) if sim["mfe_ts"] else "N/A",
    }
    results.append(result)

# Display
print("\n" + "=" * 150)
print("TIME-AWARE TRADE IDEAS")
print("=" * 150)
hdr = "RK  CONTRACT          GEN_TIME  ENTRY_WIN            ENTRY    STOP     T1       T2       MFE%   MAE%   T_MFE  T_EXIT  PNL%    HOLD_CLS   OUTCOME"
print(hdr)
print("-" * len(hdr))

for r in results:
    line = str(r["rank"]).ljust(4)
    line += (r["underlying"] + " " + str(int(r["strike"])) + " " + r["option_type"]).ljust(18)
    line += r["timestamp_generated"].ljust(10)
    line += r["entry_window"].ljust(21)
    line += str(r["entry"]).ljust(9)
    line += str(r["stop"]).ljust(9)
    line += str(r["target1"]).ljust(9)
    line += str(r["target2"]).ljust(9)
    line += str(r["mfe_pct"]).ljust(7)
    line += str(r["mae_pct"]).ljust(7)
    line += str(r["time_to_mfe_min"]).ljust(7)
    line += str(r["expected_hold"]).ljust(8)
    line += str(r["actual_pnl"]).ljust(8)
    line += r["hold_class"].ljust(11)
    line += r["actual_outcome"]
    print(line)

print("=" * 150)

# Summary
holds = [r["expected_hold"] for r in results]
median_hold = sorted(holds)[len(holds)//2] if holds else 0

best_pnl_trade = max(results, key=lambda x: x["actual_pnl"]) if results else None
best_entry = best_pnl_trade["entry_time"] if best_pnl_trade else "N/A"
best_exit = best_pnl_trade["exit_time"] if best_pnl_trade else "N/A"
best_name = (best_pnl_trade["underlying"] + " " + str(int(best_pnl_trade["strike"])) + " " + best_pnl_trade["option_type"]) if best_pnl_trade else "NONE"

# Save CSV
os.makedirs("reports", exist_ok=True)
with open("reports/time_trade_ideas.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

if median_hold < 15:
    decision = "FAST_SIGNAL"
elif median_hold < 90:
    decision = "INTRADAY_SIGNAL"
else:
    decision = "POSITIONAL_SIGNAL"

print("\nOUTPUT:")
print("ideas: " + str(len(results)))
print("median_hold: " + str(median_hold) + " min")
print("best_entry_time: " + best_entry)
print("best_exit_time: " + best_exit)
print("best_trade: " + best_name + " (+" + str(best_pnl_trade["actual_pnl"]) + "%)" if best_pnl_trade else "NONE")
print("decision: " + decision)
print("STOP")
