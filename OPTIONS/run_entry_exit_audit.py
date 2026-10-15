"""PHASE O2L — ENTRY & EXIT ENGINE AUDIT"""
import glob, os, csv, polars as pl, math
from datetime import datetime

date_str = "2026-06-19"

# Load trade ideas
ideas_csv = pl.read_csv("reports/final_trade_ideas.csv")

# Load ALL raw data
raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
dfs = [pl.read_parquet(f) for f in raw_files]
df_raw = pl.concat(dfs, how="diagonal_relaxed").sort("timestamp")
df_options = df_raw.filter(
    (pl.col("strike") > 0) & (pl.col("option_type").is_in(["CE", "PE"]))
).sort("timestamp")

print("Ideas: " + str(ideas_csv.height))
print("Option ticks: " + str(df_options.height))

def compute_atr(prices, period=14):
    """Simple ATR proxy from price list using true range approximation."""
    if len(prices) < period + 1:
        return max(prices) - min(prices) if prices else 0
    trs = []
    for i in range(1, len(prices)):
        tr = abs(prices[i] - prices[i-1])
        trs.append(tr)
    return sum(trs[-period:]) / period if trs else 0

def simulate_variant(ticks, entry_price, stop_price, t1_price, t2_price, variant):
    """Simulate one execution variant. Returns dict of results."""
    if not ticks:
        return {"triggered": False, "stopped": False, "t1": False, "t2": False,
                "pnl_pct": 0, "max_dd": 0, "hold_min": 0, "exit_price": 0}
    
    prices = [t["ltp"] for t in ticks if t.get("ltp") and t["ltp"] > 0]
    timestamps = [t["timestamp"] for t in ticks if t.get("ltp") and t["ltp"] > 0]
    
    if not prices:
        return {"triggered": False, "stopped": False, "t1": False, "t2": False,
                "pnl_pct": 0, "max_dd": 0, "hold_min": 0, "exit_price": 0}
    
    atr = compute_atr(prices)
    
    # Determine entry and stop based on variant
    in_trade = False
    actual_entry = 0
    actual_stop = 0
    entry_idx = 0
    peak_since_entry = 0
    trailing_active = False
    
    t1_hit = False
    t2_hit = False
    stopped = False
    exit_price = 0
    exit_idx = 0
    max_dd = 0
    
    for i, (price, ts) in enumerate(zip(prices, timestamps)):
        if not in_trade:
            # ENTRY LOGIC per variant
            if variant == "A":
                # Immediate entry at first available price
                actual_entry = price
                actual_stop = stop_price
                in_trade = True
                entry_idx = i
                peak_since_entry = price
                
            elif variant == "B":
                # Wait for 25% retrace from recent high
                recent_high = max(prices[max(0, i-10):i+1])
                retrace_level = recent_high * 0.975  # 2.5% pullback
                if price <= retrace_level and i > 5:
                    actual_entry = price
                    # Stop = recent swing low
                    recent_low = min(prices[max(0, i-10):i+1])
                    actual_stop = recent_low * 0.99
                    in_trade = True
                    entry_idx = i
                    peak_since_entry = price
                    
            elif variant == "C":
                # Confirmation break — price must exceed entry + 1%
                if price > entry_price * 1.01 and i > 3:
                    actual_entry = price
                    actual_stop = price - 2 * atr if atr > 0 else price * 0.90
                    in_trade = True
                    entry_idx = i
                    peak_since_entry = price
                    
            elif variant == "D":
                # Immediate entry, trailing stop after +3%
                actual_entry = price
                actual_stop = stop_price  # initial fixed stop
                in_trade = True
                entry_idx = i
                peak_since_entry = price
                trailing_active = False
        
        else:
            # IN TRADE — track and check exits
            if actual_entry <= 0:
                break
                
            pnl_now = (price - actual_entry) / actual_entry * 100
            dd = min(0, pnl_now)
            max_dd = min(max_dd, dd)
            
            if price > peak_since_entry:
                peak_since_entry = price
            
            # Variant D: activate trailing after +3%
            if variant == "D":
                gain_from_entry = (peak_since_entry - actual_entry) / actual_entry
                if gain_from_entry >= 0.03:
                    trailing_active = True
                    trailing_stop = peak_since_entry * 0.97  # trail at 3%
                    actual_stop = max(actual_stop, trailing_stop)
            
            # Check stop
            if price <= actual_stop:
                stopped = True
                exit_price = price
                exit_idx = i
                break
            
            # Check T1
            if price >= t1_price and not t1_hit:
                t1_hit = True
            
            # Check T2
            if price >= t2_price and not t2_hit:
                t2_hit = True
                exit_price = price
                exit_idx = i
                break  # Exit at T2
    
    # If still in trade at end
    if in_trade and not stopped and not t2_hit and prices:
        exit_price = prices[-1]
        exit_idx = len(prices) - 1
    
    # Compute results
    if actual_entry > 0 and exit_price > 0:
        pnl_pct = round((exit_price - actual_entry) / actual_entry * 100, 2)
    elif actual_entry > 0:
        pnl_pct = round((prices[-1] - actual_entry) / actual_entry * 100, 2)
    else:
        pnl_pct = 0
    
    hold_min = round((timestamps[exit_idx] - timestamps[entry_idx]) / 60000, 1) if in_trade and exit_idx > entry_idx else 0
    
    return {
        "triggered": in_trade,
        "stopped": stopped,
        "t1": t1_hit,
        "t2": t2_hit,
        "pnl_pct": pnl_pct,
        "max_dd": round(max_dd, 2),
        "hold_min": hold_min,
        "exit_price": round(exit_price, 2),
    }


# Run all 4 variants for each trade idea
variants = ["A", "B", "C", "D"]
variant_labels = {
    "A": "Immediate/Fixed",
    "B": "Retrace/SwingLow",
    "C": "Confirm/ATR",
    "D": "Immediate/Trailing",
}

all_results = []
variant_stats = {v: {"triggered": 0, "stopped": 0, "t1": 0, "t2": 0, "pnl_sum": 0, "wins": 0, "dd_sum": 0, "hold_sum": 0} for v in variants}

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
    ticks = df_c.to_dicts()
    
    # Use second half as forward
    mid = len(ticks) // 2
    forward_ticks = ticks[mid:] if mid > 0 else ticks
    
    best_variant = "A"
    best_pnl = -999
    
    row_result = {"rank": row_idx + 1, "contract": contract}
    
    for v in variants:
        res = simulate_variant(forward_ticks, entry_price, stop_price, t1_price, t2_price, v)
        row_result[v + "_triggered"] = res["triggered"]
        row_result[v + "_stopped"] = res["stopped"]
        row_result[v + "_t1"] = res["t1"]
        row_result[v + "_t2"] = res["t2"]
        row_result[v + "_pnl"] = res["pnl_pct"]
        row_result[v + "_dd"] = res["max_dd"]
        row_result[v + "_hold"] = res["hold_min"]
        
        if res["triggered"]:
            variant_stats[v]["triggered"] += 1
            if res["stopped"]:
                variant_stats[v]["stopped"] += 1
            if res["t1"]:
                variant_stats[v]["t1"] += 1
            if res["t2"]:
                variant_stats[v]["t2"] += 1
            variant_stats[v]["pnl_sum"] += res["pnl_pct"]
            if res["pnl_pct"] > 0:
                variant_stats[v]["wins"] += 1
            variant_stats[v]["dd_sum"] += res["max_dd"]
            variant_stats[v]["hold_sum"] += res["hold_min"]
        
        if res["pnl_pct"] > best_pnl:
            best_pnl = res["pnl_pct"]
            best_variant = v
    
    row_result["winner"] = best_variant
    all_results.append(row_result)

# Display per-trade results
print("\n" + "=" * 130)
print("PER-TRADE VARIANT COMPARISON (PnL %)")
print("=" * 130)
hdr = "RK  CONTRACT          A_PnL    A_T1  B_PnL    B_T1  C_PnL    C_T1  D_PnL    D_T1  WINNER"
print(hdr)
print("-" * len(hdr))

for r in all_results:
    line = str(r["rank"]).ljust(4)
    line += str(r["contract"]).ljust(18)
    for v in variants:
        line += str(r[v + "_pnl"]).ljust(9)
        line += ("Y" if r[v + "_t1"] else "N").ljust(6)
    line += r["winner"]
    print(line)

# Summary per variant
print("\n" + "=" * 100)
print("VARIANT SUMMARY")
print("=" * 100)
hdr2 = "VARIANT              TRIGGERED  STOPPED  T1_HITS  T2_HITS  WIN_RATE  AVG_PNL   AVG_DD    AVG_HOLD"
print(hdr2)
print("-" * len(hdr2))

best_model = "A"
best_wr = 0

for v in variants:
    s = variant_stats[v]
    trig = s["triggered"]
    wr = round(s["wins"] / trig, 4) if trig > 0 else 0
    avg_pnl = round(s["pnl_sum"] / trig, 2) if trig > 0 else 0
    avg_dd = round(s["dd_sum"] / trig, 2) if trig > 0 else 0
    avg_hold = round(s["hold_sum"] / trig, 1) if trig > 0 else 0
    survival = round((trig - s["stopped"]) / trig, 4) if trig > 0 else 0
    
    line = (v + " " + variant_labels[v]).ljust(21)
    line += str(trig).ljust(11)
    line += str(s["stopped"]).ljust(9)
    line += str(s["t1"]).ljust(9)
    line += str(s["t2"]).ljust(9)
    line += str(wr).ljust(10)
    line += str(avg_pnl).ljust(10)
    line += str(avg_dd).ljust(10)
    line += str(avg_hold)
    print(line)
    
    if wr > best_wr:
        best_wr = wr
        best_model = v

# Save CSV
os.makedirs("reports", exist_ok=True)
with open("reports/entry_exit_audit.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
    writer.writeheader()
    writer.writerows(all_results)

# Decision
current_wr = 0.0  # From O2K all stopped
improved = best_wr - current_wr

s_best = variant_stats[best_model]
trig_best = s_best["triggered"]
avg_rr_best = round(s_best["pnl_sum"] / trig_best, 2) if trig_best > 0 else 0
survival_best = round((trig_best - s_best["stopped"]) / trig_best, 4) if trig_best > 0 else 0

if improved >= 0.20:
    decision = "ENTRY_MODEL_WEAK"
elif best_wr == current_wr:
    decision = "SIGNAL_NOT_EXECUTABLE"
else:
    decision = "MIXED"

print("\nOUTPUT:")
print("best_execution_model: " + best_model + " (" + variant_labels[best_model] + ")")
print("win_rate: " + str(best_wr))
print("avg_rr: " + str(avg_rr_best))
print("survival_rate: " + str(survival_best))
print("decision: " + decision)
print("STOP")
