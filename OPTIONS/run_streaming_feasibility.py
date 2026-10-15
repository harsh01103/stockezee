"""PHASE O2R — STREAMING FEASIBILITY"""
import os, csv, polars as pl
from datetime import datetime

# Load signal data
ideas = pl.read_csv("reports/time_trade_ideas.csv")
latency = pl.read_csv("reports/signal_latency.csv")

print("Ideas: " + str(ideas.height))

def parse_time(t_str):
    try:
        parts = t_str.strip().split(":")
        return datetime(2026, 6, 19, int(parts[0]), int(parts[1]), int(parts[2]))
    except:
        return None

def parse_window(w_str):
    try:
        parts = w_str.split(" - ")
        return parse_time(parts[0]), parse_time(parts[1])
    except:
        return None, None

# Scenarios
scenarios = {
    "S1": {"flush_sec": 300, "process_sec": 60, "label": "5min flush + 60s process"},
    "S2": {"flush_sec": 60,  "process_sec": 30, "label": "1min flush + 30s process"},
    "S3": {"flush_sec": 10,  "process_sec": 10, "label": "10s flush + 10s process"},
    "S4": {"flush_sec": 0,   "process_sec": 5,  "label": "Streaming + 5s process"},
}

# For each idea, compute delivery time and usable window per scenario
all_results = []

for idx in range(ideas.height):
    r = ideas.row(idx, named=True)
    
    contract = str(r.get("underlying", "")) + " " + str(int(r.get("strike", 0))) + " " + str(r.get("option_type", ""))
    gen_time = parse_time(str(r.get("timestamp_generated", "")))
    win_start, win_end = parse_window(str(r.get("entry_window", "")))
    
    if not gen_time or not win_end:
        continue
    
    exec_window_sec = (win_end - gen_time).total_seconds()
    
    row = {"rank": idx + 1, "contract": contract, "exec_window_sec": int(exec_window_sec)}
    
    for sname, scfg in scenarios.items():
        # Total delivery latency = flush/2 (avg wait) + process time
        # For flush: on average, data arrives halfway through flush interval
        avg_flush_wait = scfg["flush_sec"] / 2.0
        total_delivery = avg_flush_wait + scfg["process_sec"]
        
        remaining = exec_window_sec - total_delivery
        usable = remaining > 0
        
        row[sname + "_delivery_sec"] = round(total_delivery)
        row[sname + "_remaining_sec"] = round(remaining)
        row[sname + "_usable"] = usable
    
    all_results.append(row)

# Display
print("\n" + "=" * 120)
print("STREAMING FEASIBILITY ANALYSIS")
print("=" * 120)
hdr = "RK  CONTRACT          EXEC_WIN  S1_DEL  S1_REM  S1_OK  S2_DEL  S2_REM  S2_OK  S3_DEL  S3_REM  S3_OK  S4_DEL  S4_REM  S4_OK"
print(hdr)
print("-" * len(hdr))

for r in all_results:
    line = str(r["rank"]).ljust(4)
    line += str(r["contract"]).ljust(18)
    line += (str(r["exec_window_sec"]) + "s").ljust(10)
    for s in scenarios:
        line += (str(r[s + "_delivery_sec"]) + "s").ljust(8)
        line += (str(r[s + "_remaining_sec"]) + "s").ljust(8)
        line += ("Y" if r[s + "_usable"] else "N").ljust(7)
    print(line)

# Scenario summaries
print("\n" + "=" * 100)
print("SCENARIO SUMMARY")
print("=" * 100)
hdr2 = "SCENARIO  LABEL                        MED_DELIVERY  USABLE_PCT  MED_REMAINING  STATUS"
print(hdr2)
print("-" * len(hdr2))

best_mode = "S1"
best_usable = 0

for sname, scfg in scenarios.items():
    deliveries = [r[sname + "_delivery_sec"] for r in all_results]
    remainings = [r[sname + "_remaining_sec"] for r in all_results]
    usable_count = sum(1 for r in all_results if r[sname + "_usable"])
    usable_pct = round(usable_count / len(all_results) * 100, 1) if all_results else 0
    
    med_del = sorted(deliveries)[len(deliveries)//2] if deliveries else 0
    med_rem = sorted(remainings)[len(remainings)//2] if remainings else 0
    
    if usable_pct >= 70:
        status = "EXECUTABLE"
    elif usable_pct >= 30:
        status = "PARTIAL"
    else:
        status = "TOO_SLOW"
    
    line = sname.ljust(10)
    line += scfg["label"].ljust(29)
    line += (str(med_del) + "s").ljust(14)
    line += (str(usable_pct) + "%").ljust(12)
    line += (str(med_rem) + "s").ljust(15)
    line += status
    print(line)
    
    if usable_pct > best_usable:
        best_usable = usable_pct
        best_mode = sname

# Save CSV
os.makedirs("reports", exist_ok=True)
with open("reports/streaming_feasibility.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
    writer.writeheader()
    writer.writerows(all_results)

# Decision
s3_pct = sum(1 for r in all_results if r["S3_usable"]) / len(all_results) * 100
s4_pct = sum(1 for r in all_results if r["S4_usable"]) / len(all_results) * 100

if s3_pct >= 70 or s4_pct >= 70:
    decision = "STREAMING_SOLVES"
elif s4_pct >= 70 and s3_pct < 70:
    decision = "ULTRA_LOW_LATENCY_REQUIRED"
else:
    # Check if even streaming can't help
    if s4_pct < 30:
        decision = "SIGNAL_TOO_SHORT"
    else:
        decision = "STREAMING_SOLVES"

# Best remaining window
best_remainings = [r[best_mode + "_remaining_sec"] for r in all_results]
best_med_remaining = sorted(best_remainings)[len(best_remainings)//2] if best_remainings else 0

print("\nOUTPUT:")
print("best_mode: " + best_mode + " (" + scenarios[best_mode]["label"] + ")")
print("usable_pct: " + str(best_usable) + "%")
print("remaining_window: " + str(best_med_remaining) + "s")
print("decision: " + decision)
print("STOP")
