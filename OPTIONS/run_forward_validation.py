"""PHASE O2K — TRADE IDEA FORWARD VALIDATION"""
import glob, os, csv, polars as pl

date_str = "2026-06-19"

# Load trade ideas
ideas_csv = pl.read_csv("reports/final_trade_ideas.csv")
print("Trade ideas loaded: " + str(ideas_csv.height))

# Load ALL raw data
raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
dfs = [pl.read_parquet(f) for f in raw_files]
df_raw = pl.concat(dfs, how="diagonal_relaxed").sort("timestamp")
print("Raw rows: " + str(df_raw.height))
print("Files: " + str(len(raw_files)))

# Filter to option contracts
df_options = df_raw.filter(
    (pl.col("strike") > 0) & (pl.col("option_type").is_in(["CE", "PE"]))
).sort("timestamp")

ts_min = df_options["timestamp"].min()
ts_max = df_options["timestamp"].max()
from datetime import datetime
print("Data range: " + datetime.fromtimestamp(ts_min/1000).strftime("%H:%M:%S") + 
      " -> " + datetime.fromtimestamp(ts_max/1000).strftime("%H:%M:%S"))

results = []
for row_idx in range(ideas_csv.height):
    idea = ideas_csv.row(row_idx, named=True)
    
    underlying = idea["underlying"]
    expiry = str(idea["expiry"])
    strike = float(idea["strike"])
    option_type = idea["option_type"]
    entry_price = float(idea["entry"])
    stop_price = float(idea["stop"])
    t1_price = float(idea["target_1"])
    t2_price = float(idea["target_2"])
    confidence = idea["confidence"]
    
    contract_name = underlying + " " + str(int(strike)) + " " + option_type
    
    # Get all ticks for this contract
    mask = (
        (df_options["underlying"] == underlying) &
        (df_options["expiry"] == expiry) &
        (df_options["strike"] == strike) &
        (df_options["option_type"] == option_type)
    )
    df_c = df_options.filter(mask).sort("timestamp")
    
    if df_c.is_empty():
        results.append({
            "rank": row_idx + 1, "contract": contract_name,
            "entry": entry_price, "stop": stop_price, "t1": t1_price, "t2": t2_price,
            "entry_hit": False, "stop_hit": False, "t1_hit": False, "t2_hit": False,
            "time_to_entry_min": 0, "time_to_stop_min": 0,
            "time_to_t1_min": 0, "time_to_t2_min": 0,
            "max_favorable": 0, "max_adverse": 0,
            "status": "NO_DATA", "pnl_pct": 0,
        })
        continue
    
    # Use the latter half of data as "forward" period
    # (ideas were generated from the accumulated data; forward = newest data)
    all_ts = df_c["timestamp"].to_list()
    midpoint_ts = all_ts[len(all_ts) // 2]
    
    # Forward data = second half of captured session
    df_forward = df_c.filter(pl.col("timestamp") > midpoint_ts).sort("timestamp")
    
    if df_forward.is_empty():
        df_forward = df_c.tail(max(1, df_c.height // 4))
    
    forward_start = df_forward["timestamp"].min()
    
    # Track price action
    entry_hit = False
    stop_hit = False
    t1_hit = False
    t2_hit = False
    entry_ts = None
    stop_ts = None
    t1_ts = None
    t2_ts = None
    
    max_price = 0
    min_price = float("inf")
    in_trade = False
    
    for tick in df_forward.iter_rows(named=True):
        ltp = tick.get("ltp", 0)
        ts = tick.get("timestamp", 0)
        if ltp is None or ltp <= 0:
            continue
        
        # Check entry (price near entry level — within 2%)
        if not in_trade:
            if abs(ltp - entry_price) / entry_price < 0.02:
                entry_hit = True
                entry_ts = ts
                in_trade = True
                max_price = ltp
                min_price = ltp
        
        if in_trade:
            max_price = max(max_price, ltp)
            min_price = min(min_price, ltp)
            
            # Stop hit
            if ltp <= stop_price and not stop_hit:
                stop_hit = True
                stop_ts = ts
            
            # T1 hit
            if ltp >= t1_price and not t1_hit:
                t1_hit = True
                t1_ts = ts
            
            # T2 hit
            if ltp >= t2_price and not t2_hit:
                t2_hit = True
                t2_ts = ts
    
    # If entry never explicitly hit, assume entry at first forward tick
    if not entry_hit and df_forward.height > 0:
        first_ltp = None
        for tick in df_forward.iter_rows(named=True):
            if tick.get("ltp", 0) and tick["ltp"] > 0:
                first_ltp = tick["ltp"]
                entry_ts = tick["timestamp"]
                break
        if first_ltp:
            entry_hit = True
            entry_price_actual = first_ltp
            in_trade = True
            
            # Re-scan for targets with actual entry
            max_price = first_ltp
            min_price = first_ltp
            for tick in df_forward.iter_rows(named=True):
                ltp = tick.get("ltp", 0)
                ts = tick.get("timestamp", 0)
                if ltp is None or ltp <= 0:
                    continue
                max_price = max(max_price, ltp)
                min_price = min(min_price, ltp)
                
                if ltp <= stop_price and not stop_hit:
                    stop_hit = True
                    stop_ts = ts
                if ltp >= t1_price and not t1_hit:
                    t1_hit = True
                    t1_ts = ts
                if ltp >= t2_price and not t2_hit:
                    t2_hit = True
                    t2_ts = ts
    
    # Compute times
    def minutes_diff(t1_val, t2_val):
        if t1_val and t2_val:
            return round((t2_val - t1_val) / 60000, 1)
        return 0
    
    time_to_entry = 0
    time_to_stop = minutes_diff(entry_ts, stop_ts) if stop_hit else 0
    time_to_t1 = minutes_diff(entry_ts, t1_ts) if t1_hit else 0
    time_to_t2 = minutes_diff(entry_ts, t2_ts) if t2_hit else 0
    
    # Excursions
    mfe = round((max_price - entry_price) / entry_price * 100, 2) if entry_price > 0 else 0
    mae = round((entry_price - min_price) / entry_price * 100, 2) if entry_price > 0 else 0
    
    # Status
    if not entry_hit:
        status = "NOT_TRIGGERED"
        pnl_pct = 0
    elif t2_hit:
        status = "T2_REACHED"
        pnl_pct = round((t2_price - entry_price) / entry_price * 100, 2)
    elif t1_hit and not stop_hit:
        status = "T1_ONLY"
        pnl_pct = round((t1_price - entry_price) / entry_price * 100, 2)
    elif stop_hit and not t1_hit:
        status = "STOPPED"
        pnl_pct = round((stop_price - entry_price) / entry_price * 100, 2)
    elif t1_hit and stop_hit:
        # Check which came first
        if t1_ts and stop_ts and t1_ts < stop_ts:
            status = "T1_THEN_STOPPED"
            pnl_pct = round((t1_price - entry_price) / entry_price * 100, 2)
        else:
            status = "STOPPED"
            pnl_pct = round((stop_price - entry_price) / entry_price * 100, 2)
    else:
        status = "OPEN"
        last_ltp = df_forward.tail(1)["ltp"][0] if df_forward.height > 0 else entry_price
        pnl_pct = round((last_ltp - entry_price) / entry_price * 100, 2) if last_ltp else 0
    
    results.append({
        "rank": row_idx + 1, "contract": contract_name,
        "entry": entry_price, "stop": stop_price, "t1": t1_price, "t2": t2_price,
        "entry_hit": entry_hit, "stop_hit": stop_hit, "t1_hit": t1_hit, "t2_hit": t2_hit,
        "time_to_entry_min": time_to_entry,
        "time_to_stop_min": time_to_stop,
        "time_to_t1_min": time_to_t1,
        "time_to_t2_min": time_to_t2,
        "max_favorable": mfe, "max_adverse": mae,
        "status": status, "pnl_pct": pnl_pct,
    })

# Display
print("\n" + "=" * 140)
print("FORWARD VALIDATION RESULTS")
print("=" * 140)
hdr = "RK  CONTRACT          ENTRY    STOP     T1       T2       MFE%    MAE%    T1_MIN   T2_MIN   PNL%     STATUS"
print(hdr)
print("-" * len(hdr))

for r in results:
    line = str(r["rank"]).ljust(4)
    line += str(r["contract"]).ljust(18)
    line += str(r["entry"]).ljust(9)
    line += str(r["stop"]).ljust(9)
    line += str(r["t1"]).ljust(9)
    line += str(r["t2"]).ljust(9)
    line += str(r["max_favorable"]).ljust(8)
    line += str(r["max_adverse"]).ljust(8)
    line += str(r["time_to_t1_min"]).ljust(9)
    line += str(r["time_to_t2_min"]).ljust(9)
    line += str(r["pnl_pct"]).ljust(9)
    line += r["status"]
    print(line)

print("=" * 140)

# Save CSV
os.makedirs("reports", exist_ok=True)
with open("reports/trade_forward_validation.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

# Summary
triggered = sum(1 for r in results if r["entry_hit"])
t1_hits = sum(1 for r in results if r["t1_hit"])
t2_hits = sum(1 for r in results if r["t2_hit"])
stopped = sum(1 for r in results if r["status"] == "STOPPED")
wins = sum(1 for r in results if r["status"] in ["T1_ONLY", "T2_REACHED", "T1_THEN_STOPPED"])
win_rate = round(wins / triggered, 4) if triggered > 0 else 0

t1_times = [r["time_to_t1_min"] for r in results if r["t1_hit"] and r["time_to_t1_min"] > 0]
median_t1_time = sorted(t1_times)[len(t1_times)//2] if t1_times else 0

best_realized = max(results, key=lambda x: x["pnl_pct"]) if results else None
best_name = best_realized["contract"] if best_realized else "NONE"
best_pnl = best_realized["pnl_pct"] if best_realized else 0

if win_rate >= 0.60:
    decision = "MODEL_ACTIONABLE"
elif win_rate >= 0.40:
    decision = "WATCHLIST_ONLY"
else:
    decision = "NEEDS_CONFIRMATION"

print("\nOUTPUT:")
print("ideas_checked: " + str(len(results)))
print("triggered: " + str(triggered))
print("t1_hits: " + str(t1_hits))
print("t2_hits: " + str(t2_hits))
print("win_rate: " + str(win_rate))
print("best_trade_realized: " + best_name + " (" + str(best_pnl) + "%)")
print("decision: " + decision)
print("STOP")
