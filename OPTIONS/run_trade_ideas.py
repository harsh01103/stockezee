"""PHASE O2J — TRADE IDEA GENERATOR"""
import glob, os, csv, polars as pl
import logging
logging.getLogger("universe").setLevel(logging.ERROR)

date_str = "2026-06-19"

# Load executable contracts
exec_csv = pl.read_csv("reports/executable_trade_ideas.csv")
top_contracts = []
for r in exec_csv.head(10).iter_rows(named=True):
    top_contracts.append({
        "underlying": r["underlying"],
        "expiry": str(r["expiry"]),
        "strike": float(r["strike"]),
        "option_type": r["option_type"],
        "confidence": r["confidence"],
        "exec_score": r["execution_score"],
        "times_repeated": r["times_repeated"],
    })

print("Loading " + str(len(top_contracts)) + " executable contracts")

# Load raw data for latest prices
raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
dfs = [pl.read_parquet(f) for f in raw_files]
df_raw = pl.concat(dfs, how="diagonal_relaxed")

# Get latest snapshot per contract
df_options = df_raw.filter(
    (pl.col("strike") > 0) & (pl.col("option_type").is_in(["CE", "PE"]))
).sort("timestamp")

print("Option rows: " + str(df_options.height))
print("Columns: " + str(df_options.columns))

# Build trade ideas
ideas = []
for idx, contract in enumerate(top_contracts):
    mask = (
        (df_options["underlying"] == contract["underlying"]) &
        (df_options["expiry"] == contract["expiry"]) &
        (df_options["strike"] == contract["strike"]) &
        (df_options["option_type"] == contract["option_type"])
    )
    df_c = df_options.filter(mask).sort("timestamp")
    
    if df_c.is_empty():
        print("  SKIP: " + contract["underlying"] + " " + str(contract["strike"]) + " " + contract["option_type"] + " — no raw data")
        continue
    
    # Latest row for current prices
    latest = df_c.tail(1).row(0, named=True)
    
    # Get LTP, bid, ask
    ltp = latest.get("ltp", 0) or 0
    bid = latest.get("bid", 0) or 0
    ask = latest.get("ask", 0) or 0
    volume = latest.get("volume", 0) or 0
    oi = latest.get("oi", 0) or 0
    
    # Mid price as entry
    if bid > 0 and ask > 0:
        entry = round((bid + ask) / 2, 2)
    elif ltp > 0:
        entry = round(ltp, 2)
    else:
        print("  SKIP: " + contract["underlying"] + " " + str(contract["strike"]) + " — no price data")
        continue
    
    if entry <= 0:
        continue
    
    # Spread in absolute and percentage
    spread_abs = round(ask - bid, 2) if (bid > 0 and ask > 0) else 0
    spread_pct = round(spread_abs / entry * 100, 4) if entry > 0 else 0
    
    # Historical prices for support
    ltps = [r for r in df_c["ltp"].to_list() if r is not None and r > 0]
    recent_low = min(ltps[-20:]) if len(ltps) >= 20 else min(ltps) if ltps else entry * 0.90
    
    # Stop loss
    stop = round(max(entry * 0.92, recent_low * 0.98), 2)
    
    # Targets
    target_1 = round(entry * 1.08, 2)
    target_2 = round(entry * 1.15, 2)
    
    # Risk reward
    risk = entry - stop
    reward = target_2 - entry
    rr = round(reward / risk, 2) if risk > 0 else 0
    
    # Direction
    direction = "BEARISH" if contract["option_type"] == "PE" else "BULLISH"
    
    # Holding window based on repeat persistence
    reps = contract["times_repeated"]
    if reps <= 5:
        holding = "INTRADAY"
    elif reps <= 15:
        holding = "SWING"
    else:
        holding = "EXTENDED"
    
    # Thesis
    thesis = direction + " via " + contract["underlying"] + " " + str(int(contract["strike"])) + " " + contract["option_type"]
    thesis += " | conf=" + str(contract["confidence"])
    thesis += " | " + str(reps) + " repeats"
    thesis += " | vol=" + str(int(volume))
    
    # Rejection flags (reporting only)
    reject_reasons = []
    if spread_pct > 1.0:
        reject_reasons.append("SPREAD>" + str(round(spread_pct, 1)) + "%")
    if rr < 1.5:
        reject_reasons.append("RR<1.5")
    
    idea = {
        "rank": idx + 1,
        "underlying": contract["underlying"],
        "expiry": contract["expiry"],
        "strike": contract["strike"],
        "option_type": contract["option_type"],
        "direction": direction,
        "entry": entry,
        "stop": stop,
        "target_1": target_1,
        "target_2": target_2,
        "risk_reward": rr,
        "confidence": contract["confidence"],
        "volume": int(volume),
        "spread": spread_abs,
        "spread_pct": spread_pct,
        "holding_window": holding,
        "thesis": thesis,
        "reject_flags": "|".join(reject_reasons) if reject_reasons else "NONE",
    }
    ideas.append(idea)

# Display
print("\n" + "=" * 140)
print("TRADE IDEAS")
print("=" * 140)

hdr = "RK  UNDERLYING  EXPIRY      STRIKE    TYPE  DIR       ENTRY     STOP      T1        T2        RR     CONF    VOL         SPR%    HOLD      REJECT"
print(hdr)
print("-" * len(hdr))

for idea in ideas:
    line = str(idea["rank"]).ljust(4)
    line += str(idea["underlying"]).ljust(12)
    line += str(idea["expiry"]).ljust(12)
    line += str(idea["strike"]).ljust(10)
    line += str(idea["option_type"]).ljust(6)
    line += str(idea["direction"]).ljust(10)
    line += str(idea["entry"]).ljust(10)
    line += str(idea["stop"]).ljust(10)
    line += str(idea["target_1"]).ljust(10)
    line += str(idea["target_2"]).ljust(10)
    line += str(idea["risk_reward"]).ljust(7)
    line += str(idea["confidence"]).ljust(8)
    line += str(idea["volume"]).ljust(12)
    line += str(idea["spread_pct"]).ljust(8)
    line += str(idea["holding_window"]).ljust(10)
    line += str(idea["reject_flags"])
    print(line)

print("=" * 140)

# Save CSV
os.makedirs("reports", exist_ok=True)
with open("reports/final_trade_ideas.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=ideas[0].keys())
    writer.writeheader()
    writer.writerows(ideas)

# Clean ideas (no rejection flags)
clean_ideas = [i for i in ideas if i["reject_flags"] == "NONE"]
all_ideas = len(ideas)

best = ideas[0] if ideas else None

if all_ideas == 0:
    decision = "NO_TRADE"
elif all_ideas <= 3:
    decision = "HIGH_SELECTIVITY"
else:
    decision = "TRADE_IDEAS_READY"

print("\nOUTPUT:")
print("ideas: " + str(all_ideas))
if best:
    print("best_trade: " + best["underlying"] + " " + str(best["strike"]) + " " + best["option_type"])
    print("entry: " + str(best["entry"]))
    print("stop: " + str(best["stop"]))
    print("target_1: " + str(best["target_1"]))
    print("target_2: " + str(best["target_2"]))
    print("holding_window: " + best["holding_window"])
print("decision: " + decision)
print("STOP")
