"""PHASE O2P — SIGNAL TIMELINE INTEGRITY"""
import os, csv, polars as pl
from datetime import datetime, timedelta

# Current IST
current_ist = datetime(2026, 6, 19, 12, 33, 0)
print("Current IST: " + current_ist.strftime("%H:%M:%S"))

# Load time trade ideas
ideas = pl.read_csv("reports/time_trade_ideas.csv")
print("Ideas loaded: " + str(ideas.height))

def parse_time(t_str):
    """Parse HH:MM:SS to datetime on today."""
    try:
        parts = t_str.strip().split(":")
        return datetime(2026, 6, 19, int(parts[0]), int(parts[1]), int(parts[2]))
    except:
        return None

def parse_window(w_str):
    """Parse 'HH:MM:SS - HH:MM:SS' entry window."""
    try:
        parts = w_str.split(" - ")
        start = parse_time(parts[0])
        end = parse_time(parts[1])
        return start, end
    except:
        return None, None

results = []
for idx in range(ideas.height):
    r = ideas.row(idx, named=True)
    
    contract = r.get("underlying", "") + " " + str(int(r.get("strike", 0))) + " " + str(r.get("option_type", ""))
    
    gen_time = parse_time(str(r.get("timestamp_generated", "")))
    entry_win = str(r.get("entry_window", ""))
    win_start, win_end = parse_window(entry_win)
    entry_time = parse_time(str(r.get("entry_time", "")))
    exit_time = parse_time(str(r.get("exit_time", "")))
    
    # Lead time
    lead_min = round((win_start - gen_time).total_seconds() / 60, 1) if (win_start and gen_time) else 0
    
    # Lag to now
    lag_min = round((current_ist - gen_time).total_seconds() / 60, 1) if gen_time else 0
    
    # Classification
    if win_start and gen_time and win_start < gen_time:
        classification = "LOOKAHEAD_BIAS"
    elif win_end and current_ist > win_end:
        classification = "EXPIRED"
    elif win_end and current_ist <= win_end:
        classification = "LIVE"
    else:
        classification = "UNKNOWN"
    
    result = {
        "rank": r.get("rank", idx + 1),
        "contract": contract,
        "signal_generated_at": gen_time.strftime("%H:%M:%S") if gen_time else "N/A",
        "entry_window_start": win_start.strftime("%H:%M:%S") if win_start else "N/A",
        "entry_window_end": win_end.strftime("%H:%M:%S") if win_end else "N/A",
        "entry_time": entry_time.strftime("%H:%M:%S") if entry_time else "N/A",
        "exit_time": exit_time.strftime("%H:%M:%S") if exit_time else "N/A",
        "lead_time_min": lead_min,
        "lag_to_now_min": lag_min,
        "classification": classification,
    }
    results.append(result)

# Display
print("\n" + "=" * 130)
print("SIGNAL TIMELINE INTEGRITY")
print("=" * 130)
hdr = "RK  CONTRACT          GENERATED  WIN_START  WIN_END    ENTRY      EXIT       LEAD_MIN  LAG_MIN   STATUS"
print(hdr)
print("-" * len(hdr))

for r in results:
    line = str(r["rank"]).ljust(4)
    line += str(r["contract"]).ljust(18)
    line += str(r["signal_generated_at"]).ljust(11)
    line += str(r["entry_window_start"]).ljust(11)
    line += str(r["entry_window_end"]).ljust(11)
    line += str(r["entry_time"]).ljust(11)
    line += str(r["exit_time"]).ljust(11)
    line += str(r["lead_time_min"]).ljust(10)
    line += str(r["lag_to_now_min"]).ljust(10)
    line += r["classification"]
    print(line)

print("=" * 130)

# Metrics
live_count = sum(1 for r in results if r["classification"] == "LIVE")
expired_count = sum(1 for r in results if r["classification"] == "EXPIRED")
lookahead_count = sum(1 for r in results if r["classification"] == "LOOKAHEAD_BIAS")

# Save CSV
os.makedirs("reports", exist_ok=True)
with open("reports/signal_timeline_integrity.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

# Decision
if lookahead_count > 0:
    decision = "LOOKAHEAD_DETECTED"
elif live_count > 0:
    decision = "LIVE_SIGNALS_EXIST"
elif expired_count == len(results):
    decision = "ALL_EXPIRED"
else:
    decision = "CLEAN"

print("\nOUTPUT:")
print("ideas: " + str(len(results)))
print("live: " + str(live_count))
print("expired: " + str(expired_count))
print("lookahead: " + str(lookahead_count))
print("decision: " + decision)
print("STOP")
