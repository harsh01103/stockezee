import time
import json
import subprocess
from pathlib import Path
import sys

def main():
    print("Starting recorder...", flush=True)
    proc = subprocess.Popen([sys.executable, "recorder.py", "--resume", "--dry-run"])
    
    heartbeat_file = Path("runtime/heartbeat.json")
    reports_dir = Path("reports")
    
    print("Observing for 180 seconds...", flush=True)
    for i in range(12):
        time.sleep(15)
        if heartbeat_file.exists():
            try:
                with open(heartbeat_file, "r") as f:
                    hb = json.load(f)
                print(f"[{15*(i+1)}s] Heartbeat: {hb}", flush=True)
            except Exception as e:
                print(f"[{15*(i+1)}s] Could not read heartbeat: {e}", flush=True)
        else:
            print(f"[{15*(i+1)}s] No heartbeat yet", flush=True)
            
    print("Stopping recorder...", flush=True)
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        
    print("\n--- FINAL REPORT METRICS ---", flush=True)
    # Check reports
    try:
        report_files = list(reports_dir.glob("session_report_*.json"))
        if report_files:
            latest_report = max(report_files, key=lambda p: p.stat().st_mtime)
            with open(latest_report, "r") as f:
                rep = json.load(f)
            print(f"Validator Report: {json.dumps(rep, indent=2)}")
    except Exception as e:
        print(f"Could not read validator report: {e}")
        
    # Check data/events
    events_dir = Path("data/events")
    events_count = 0
    if events_dir.exists():
        for day in events_dir.iterdir():
            if day.is_dir():
                events_count += len(list(day.glob("*.parquet")))
    print(f"Events files count: {events_count}")
    
    raw_dir = Path("data/raw")
    raw_count = 0
    if raw_dir.exists():
        for day in raw_dir.iterdir():
            if day.is_dir():
                raw_count += len(list(day.glob("*.parquet")))
    print(f"Raw ticks files count: {raw_count}")

if __name__ == "__main__":
    main()
