"""PHASE O2M — TRAILING EXIT ROBUSTNESS"""
import glob, os, csv, polars as pl

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

# Trailing variants
trail_configs = {
    "D1": {"activation_pct": 0.02, "trail_pct": 0.02, "label": "Trail after +2%, trail 2%"},
    "D2": {"activation_pct": 0.03, "trail_pct": 0.03, "label": "Trail after +3%, trail 3%"},
    "D3": {"activation_pct": 0.05, "trail_pct": 0.04, "label": "Trail after +5%, trail 4%"},
    "D4": {"activation_pct": 0.07, "trail_pct": 0.05, "label": "Trail after +7%, trail 5%"},
}

def simulate_trailing(prices, timestamps, entry_price, stop_price, t1_price, t2_price, activation_pct, trail_pct):
    if not prices:
        return {"triggered": False, "win": False, "pnl": 0, "dd": 0, "hold": 0, "t1": False, "t2": False}
    
    actual_entry = prices[0]
    actual_stop = stop_price
    peak = actual_entry
    trailing_active = False
    t1_hit = False
    t2_hit = False
    exit_price = prices[-1]
    exit_idx = len(prices) - 1
    stopped = False
    
    for i in range(1, len(prices)):
        p = prices[i]
        
        # Update peak
        if p > peak:
            peak = p
        
        # Check trailing activation
        gain = (peak - actual_entry) / actual_entry
        if gain >= activation_pct:
            trailing_active = True
            trail_stop = peak * (1 - trail_pct)
            actual_stop = max(actual_stop, trail_stop)
        
        # Check stop
        if p <= actual_stop:
            stopped = True
            exit_price = p
            exit_idx = i
            break
        
        # Check targets
        if p >= t1_price:
            t1_hit = True
        if p >= t2_price:
            t2_hit = True
            exit_price = p
            exit_idx = i
            break
    
    pnl = round((exit_price - actual_entry) / actual_entry * 100, 2) if actual_entry > 0 else 0
    max_dd = 0
    for i in range(1, exit_idx + 1):
        dd = (prices[i] - actual_entry) / actual_entry * 100
        if dd < max_dd:
            max_dd = dd
    max_dd = round(max_dd, 2)
    hold = round((timestamps[exit_idx] - timestamps[0]) / 60000, 1) if exit_idx > 0 else 0
    win = pnl > 0
    
    return {"triggered": True, "win": win, "pnl": pnl, "dd": max_dd, "hold": hold,
            "t1": t1_hit, "t2": t2_hit, "stopped": stopped}

# Run all variants
variant_results = {v: [] for v in trail_configs}
per_trade_results = []

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
    all_ts = [r for r in df_c["timestamp"].to_list()]
    
    # Use second half as forward
    mid = len(all_prices) // 2
    fwd_prices = all_prices[mid:] if mid > 0 else all_prices
    fwd_ts = all_ts[mid:] if mid > 0 else all_ts
    
    trade_row = {"rank": row_idx + 1, "contract": contract}
    
    for vname, vcfg in trail_configs.items():
        res = simulate_trailing(
            fwd_prices, fwd_ts, entry_price, stop_price, t1_price, t2_price,
            vcfg["activation_pct"], vcfg["trail_pct"]
        )
        variant_results[vname].append(res)
        trade_row[vname + "_pnl"] = res["pnl"]
        trade_row[vname + "_win"] = res["win"]
        trade_row[vname + "_dd"] = res["dd"]
        trade_row[vname + "_hold"] = res["hold"]
        trade_row[vname + "_t1"] = res["t1"]
    
    per_trade_results.append(trade_row)

# Per-trade display
print("\n" + "=" * 110)
print("PER-TRADE TRAILING COMPARISON (PnL %)")
print("=" * 110)
hdr = "RK  CONTRACT          D1(+2%)   D2(+3%)   D3(+5%)   D4(+7%)   BEST"
print(hdr)
print("-" * len(hdr))

for r in per_trade_results:
    best_v = max(trail_configs.keys(), key=lambda v: r[v + "_pnl"])
    line = str(r["rank"]).ljust(4)
    line += str(r["contract"]).ljust(18)
    for v in trail_configs:
        line += str(r[v + "_pnl"]).ljust(10)
    line += best_v
    print(line)

# Variant summary
print("\n" + "=" * 110)
print("VARIANT SUMMARY")
print("=" * 110)
hdr2 = "VARIANT  LABEL                       TRIG  WINS  WIN_RATE  AVG_PNL   AVG_DD    MED_HOLD  PROFIT_FAC  MAX_CONS_LOSS"
print(hdr2)
print("-" * len(hdr2))

variant_summaries = {}
for vname, vcfg in trail_configs.items():
    results = variant_results[vname]
    triggered = sum(1 for r in results if r["triggered"])
    wins = sum(1 for r in results if r["win"])
    losses = triggered - wins
    wr = round(wins / triggered, 4) if triggered > 0 else 0
    
    pnls = [r["pnl"] for r in results if r["triggered"]]
    avg_pnl = round(sum(pnls) / len(pnls), 2) if pnls else 0
    avg_dd = round(sum(r["dd"] for r in results if r["triggered"]) / triggered, 2) if triggered > 0 else 0
    
    holds = sorted([r["hold"] for r in results if r["triggered"]])
    med_hold = holds[len(holds)//2] if holds else 0
    
    # Profit factor
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    pf = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (999 if gross_profit > 0 else 0)
    
    # Max consecutive losses
    max_cl = 0
    cl = 0
    for r in results:
        if r["triggered"] and not r["win"]:
            cl += 1
            max_cl = max(max_cl, cl)
        else:
            cl = 0
    
    variant_summaries[vname] = {
        "wr": wr, "avg_pnl": avg_pnl, "pf": pf, "avg_dd": avg_dd,
        "med_hold": med_hold, "max_cl": max_cl, "triggered": triggered,
        "wins": wins,
    }
    
    line = vname.ljust(9)
    line += vcfg["label"].ljust(28)
    line += str(triggered).ljust(6)
    line += str(wins).ljust(6)
    line += str(wr).ljust(10)
    line += str(avg_pnl).ljust(10)
    line += str(avg_dd).ljust(10)
    line += str(med_hold).ljust(10)
    line += str(pf).ljust(12)
    line += str(max_cl)
    print(line)

# Stability score: std of win_rates across variants
win_rates = [variant_summaries[v]["wr"] for v in trail_configs]
avg_wr = sum(win_rates) / len(win_rates)
wr_std = (sum((w - avg_wr)**2 for w in win_rates) / len(win_rates)) ** 0.5
stability_score = round(1.0 - wr_std, 4)  # Higher = more stable

# Find best variant
best_v = max(trail_configs.keys(), key=lambda v: variant_summaries[v]["wr"] * 100 + variant_summaries[v]["pf"])
best_s = variant_summaries[best_v]

# Decision
wr_range = max(win_rates) - min(win_rates)
if wr_range > 0.20:
    decision = "OVERFIT_EXIT"
elif abs(variant_summaries["D2"]["wr"] - variant_summaries["D3"]["wr"]) <= 0.15:
    decision = "ROBUST_EXIT"
else:
    all_fail = all(s["wr"] < 0.3 for s in variant_summaries.values())
    if all_fail:
        decision = "SIGNAL_NOT_STABLE"
    else:
        decision = "MIXED"

# Save CSV
os.makedirs("reports", exist_ok=True)
with open("reports/trailing_robustness.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=per_trade_results[0].keys())
    writer.writeheader()
    writer.writerows(per_trade_results)

print("\nOUTPUT:")
print("best_variant: " + best_v + " (" + trail_configs[best_v]["label"] + ")")
print("win_rate: " + str(best_s["wr"]))
print("avg_rr: " + str(best_s["avg_pnl"]))
print("profit_factor: " + str(best_s["pf"]))
print("stability_score: " + str(stability_score))
print("decision: " + decision)
print("STOP")
