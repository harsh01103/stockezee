"""PHASE O2Q — SIGNAL DELIVERY LATENCY"""
import glob, os, csv, polars as pl
from datetime import datetime

date_str = "2026-06-19"

# Load time trade ideas for signal generation times
ideas = pl.read_csv("reports/time_trade_ideas.csv")

# Load raw data to compute capture timestamps
raw_files = sorted(glob.glob(f"data/raw/{date_str}/*.parquet"))
dfs = [pl.read_parquet(f) for f in raw_files]
df_raw = pl.concat(dfs, how="diagonal_relaxed").sort("timestamp")
df_options = df_raw.filter(
    (pl.col("strike") > 0) & (pl.col("option_type").is_in(["CE", "PE"]))
).sort("timestamp")

print("Ideas: " + str(ideas.height))
print("Raw files: " + str(len(raw_files)))

# File timestamps (flush times from recorder — proxy for capture latency)
file_flush_times = []
for f in raw_files:
    # Extract time from filename like 05_02_e73b46.parquet -> 05:02
    basename = os.path.basename(f)
    parts = basename.split("_")
    if len(parts) >= 2:
        try:
            h = int(parts[0])
            m = int(parts[1])
            flush_ts = datetime(2026, 6, 19, h, m, 0)
            # Convert to IST (files are in UTC, add 5:30)
            flush_ist = datetime(2026, 6, 19, h + 5, m + 30, 0)
            if flush_ist.hour >= 24:
                flush_ist = flush_ist.replace(hour=flush_ist.hour - 24)
            file_flush_times.append(flush_ist)
        except:
            pass

print("Flush times (IST): " + str([f.strftime("%H:%M") for f in sorted(file_flush_times)]))

# Pipeline stages timing:
# 1. Market event -> Upstox WebSocket -> recorder receives (capture_latency ~0)
# 2. Recorder buffers -> flush to parquet every 5 min (capture_latency = 0-300s)
# 3. Process features + research + universe + scorer + confidence (processing_latency)
# 4. Human reviews output (decision_latency)
# 5. Trade idea generated

# Estimate processing latency from actual run times
# The pipeline runs took ~10-15 seconds (from task logs)
PIPELINE_PROCESSING_SECONDS = 15  # from observed run times
HUMAN_DECISION_SECONDS = 0  # automated, no human in loop

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

# The trade idea script was run at ~12:07 IST (from task completion time 06:37 UTC + 5:30)
TRADE_IDEA_CREATED_IST = datetime(2026, 6, 19, 12, 7, 45)

results = []
for idx in range(ideas.height):
    r = ideas.row(idx, named=True)
    
    contract = str(r.get("underlying", "")) + " " + str(int(r.get("strike", 0))) + " " + str(r.get("option_type", ""))
    
    gen_time = parse_time(str(r.get("timestamp_generated", "")))
    win_start, win_end = parse_window(str(r.get("entry_window", "")))
    
    if not gen_time or not win_end:
        continue
    
    # Execution window = entry_window_end - signal_generated_at
    exec_window_sec = round((win_end - gen_time).total_seconds())
    
    # Capture latency: time from market event to nearest parquet flush
    # The signal was generated from data that was flushed before gen_time
    # Find the last flush before gen_time
    prior_flushes = [f for f in sorted(file_flush_times) if f <= gen_time]
    if prior_flushes:
        last_flush = prior_flushes[-1]
        capture_latency_sec = round((gen_time - last_flush).total_seconds())
    else:
        capture_latency_sec = 300  # worst case = full flush interval
    
    # Processing latency: pipeline run time
    processing_latency_sec = PIPELINE_PROCESSING_SECONDS
    
    # Decision latency: time from signal detection to trade idea creation
    decision_latency_sec = round((TRADE_IDEA_CREATED_IST - gen_time).total_seconds())
    
    # Total pipeline latency = trade_idea_created_at - signal_generated_at
    pipeline_latency_sec = decision_latency_sec
    
    # Usable window = execution_window - pipeline_latency
    usable_window_sec = exec_window_sec - pipeline_latency_sec
    
    # Classification
    if usable_window_sec > 0:
        classification = "LIVE_EXECUTABLE"
    elif pipeline_latency_sec > exec_window_sec:
        classification = "TOO_LATE"
    else:
        classification = "MISSED"
    
    result = {
        "rank": idx + 1,
        "contract": contract,
        "signal_generated": gen_time.strftime("%H:%M:%S"),
        "entry_window_end": win_end.strftime("%H:%M:%S"),
        "trade_idea_created": TRADE_IDEA_CREATED_IST.strftime("%H:%M:%S"),
        "execution_window_sec": exec_window_sec,
        "capture_latency_sec": capture_latency_sec,
        "processing_latency_sec": processing_latency_sec,
        "decision_latency_sec": decision_latency_sec,
        "pipeline_latency_sec": pipeline_latency_sec,
        "usable_window_sec": usable_window_sec,
        "classification": classification,
    }
    results.append(result)

# Display
print("\n" + "=" * 140)
print("SIGNAL DELIVERY LATENCY")
print("=" * 140)
hdr = "RK  CONTRACT          GENERATED  WIN_END    CREATED    EXEC_WIN  CAPT_LAT  PROC_LAT  PIPE_LAT  USABLE    STATUS"
print(hdr)
print("-" * len(hdr))

for r in results:
    line = str(r["rank"]).ljust(4)
    line += str(r["contract"]).ljust(18)
    line += str(r["signal_generated"]).ljust(11)
    line += str(r["entry_window_end"]).ljust(11)
    line += str(r["trade_idea_created"]).ljust(11)
    line += (str(r["execution_window_sec"]) + "s").ljust(10)
    line += (str(r["capture_latency_sec"]) + "s").ljust(10)
    line += (str(r["processing_latency_sec"]) + "s").ljust(10)
    line += (str(r["pipeline_latency_sec"]) + "s").ljust(10)
    line += (str(r["usable_window_sec"]) + "s").ljust(10)
    line += r["classification"]
    print(line)

print("=" * 140)

# Metrics
windows = [r["execution_window_sec"] for r in results]
latencies = [r["pipeline_latency_sec"] for r in results]
usable = [r["usable_window_sec"] for r in results]
usable_count = sum(1 for r in results if r["classification"] == "LIVE_EXECUTABLE")
usable_pct = round(usable_count / len(results) * 100, 1) if results else 0

median_window = sorted(windows)[len(windows)//2] if windows else 0
median_latency = sorted(latencies)[len(latencies)//2] if latencies else 0

# Save CSV
os.makedirs("reports", exist_ok=True)
with open("reports/signal_latency.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

if usable_pct >= 70:
    decision = "REALTIME_READY"
elif usable_pct >= 30:
    decision = "NEEDS_ACCELERATION"
else:
    decision = "POST_FACTO_SYSTEM"

print("\nOUTPUT:")
print("signals: " + str(len(results)))
print("median_window: " + str(median_window) + "s")
print("median_latency: " + str(median_latency) + "s")
print("usable_pct: " + str(usable_pct) + "%")
print("decision: " + decision)
print("STOP")
