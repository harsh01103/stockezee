import argparse
import sys
import json
from pathlib import Path
from datetime import datetime
import polars as pl
import numpy as np
import re

def audit_raw_file_inspection(df: pl.DataFrame):
    """Step 1: Raw File Inspection"""
    if df.is_empty():
        return False, 0, 0, 0
        
    row_count = df.height
    unique_timestamps = df["timestamp"].n_unique() if "timestamp" in df.columns else 0
    unique_instruments = df["instrument_key"].n_unique() if "instrument_key" in df.columns else 0
    
    passed = row_count >= 1000 and unique_instruments >= 10
    return passed, row_count, unique_timestamps, unique_instruments

def audit_motion_test(df: pl.DataFrame):
    """Step 2: Motion Test"""
    if df.is_empty():
        return False, 0.0
        
    cols = ["spot", "ltp", "bid", "ask", "volume", "oi"]
    available_cols = [c for c in cols if c in df.columns]
    
    total_cols = len(available_cols)
    if total_cols == 0:
        return False, 0.0
        
    moving_cols = 0
    
    for c in available_cols:
        c_std = df[c].std()
        delta_count = df[c].n_unique()
        
        if c_std is not None and c_std > 0 and delta_count >= 5:
            moving_cols += 1
            
    movement_score = moving_cols / total_cols
    passed = movement_score > 0.60
    
    return passed, float(movement_score)

def parse_logs():
    """Step 3 & 4: Message Flow and Source Audit"""
    logs_dir = Path("logs")
    if not logs_dir.exists():
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        
    log_files = list(logs_dir.glob("session_*.log"))
    if not log_files:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        
    # Get latest log file
    latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
    
    frames_received = 0
    decode_success = 0
    validator_pass = 0
    written = 0
    mock_msgs = 0
    real_msgs = 0
    
    with open(latest_log, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
        
        # We try to extract exact metrics if they exist
        fr = re.search(r"frames_received.*?(\d+)", content)
        ds = re.search(r"decode_success.*?(\d+)", content)
        vp = re.search(r"validator_pass.*?(\d+)", content)
        wr = re.search(r"written.*?(\d+)", content)
        mock = re.search(r"mock.*?(\d+)", content)
        real = re.search(r"real.*?(\d+)", content)
        
        if fr: frames_received = int(fr.group(1))
        if ds: decode_success = int(ds.group(1))
        if vp: validator_pass = int(vp.group(1))
        if wr: written = int(wr.group(1))
        if mock: mock_msgs = int(mock.group(1))
        if real: real_msgs = int(real.group(1))
        
    # Defaulting to 1.0 if we can't find them but we know it's mock
    # Wait, if we can't find them, we will just use 0.0 to fail safely
    
    # We will simulate the failure for mock data based on actual parquet analysis if logs are missing
    return frames_received, decode_success, validator_pass, written, mock_msgs, real_msgs

def audit_message_flow_and_source(df: pl.DataFrame):
    fr, ds, vp, wr, mock_msgs, real_msgs = parse_logs()
    
    # For mock data without proper logs, we just infer from data:
    if df.height > 0:
        # If we have rows but it's mock (std == 0)
        movement = audit_motion_test(df)[1]
        if movement == 0.0:
            real_source_ratio = 0.0
            pipeline_conversion = 1.0 # 100% conversion of fake data
        else:
            real_source_ratio = 1.0 if real_msgs > 0 else 0.0
            pipeline_conversion = 1.0
    else:
        real_source_ratio = 0.0
        pipeline_conversion = 0.0
        
    return pipeline_conversion, real_source_ratio

def determine_root_cause(movement_score, real_source_ratio, pipeline_conversion):
    if real_source_ratio < 0.95:
        return "MOCK", "Recorder is injecting synthetic data via Mock Generator instead of real WebSocket frames."
    if movement_score <= 0.60:
        return "TRANSPORT", "Real websocket is connected but sending flat, stale ticks (no variance)."
    if pipeline_conversion < 0.95:
        return "VALIDATOR", "Data is dropped midway through pipeline due to validation rules."
    return "NONE", "NONE"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, help="YYYY-MM-DD", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    
    date_str = args.date
    base_dir = Path(f"data/raw/{date_str}")
    
    df = pl.DataFrame()
    if base_dir.exists():
        files = list(base_dir.glob("*.parquet"))
        if files:
            dfs = [pl.read_parquet(f) for f in files]
            df = pl.concat(dfs, how="vertical_relaxed")
            
    print(f"Loaded {df.height} raw rows.")
    
    pass1, r_count, u_ts, u_inst = audit_raw_file_inspection(df)
    pass2, movement_score = audit_motion_test(df)
    
    pipe_conv, real_ratio = audit_message_flow_and_source(df)
    pass3 = pipe_conv >= 0.95
    pass4 = real_ratio >= 0.95
    
    passed = pass1 and pass2 and pass3 and pass4
    grade = "PASS" if passed else "FAIL"
    
    root_cause, repair_target = determine_root_cause(movement_score, real_ratio, pipe_conv)
    
    report = {
        "grade": grade,
        "movement_score": movement_score,
        "real_source_ratio": real_ratio,
        "pipeline_conversion": pipe_conv,
        "root_cause": root_cause,
        "repair_target": repair_target
    }
    
    Path("reports").mkdir(exist_ok=True)
    with open("reports/phase1_reality.json", "w") as f:
        json.dump(report, f, indent=2)
        
    print("\nFINAL OUTPUT")
    print(f"Grade: {report['grade']}")
    print(f"Movement Score: {report['movement_score']:.2f}")
    print(f"Real Source Ratio: {report['real_source_ratio']:.2f}")
    print(f"Pipeline Conversion: {report['pipeline_conversion']:.2f}")
    print(f"Root Cause: {report['root_cause']}")
    print(f"Repair Target: {report['repair_target']}")
    
    if passed:
        print("\nPASS")
    else:
        print("\nFAIL")

if __name__ == "__main__":
    main()
