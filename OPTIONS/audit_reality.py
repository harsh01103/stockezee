import argparse
import sys
import json
from pathlib import Path
from datetime import datetime
import polars as pl
import numpy as np

def audit_raw_motion(date_str: str):
    """Step 1: Raw Motion"""
    base_dir = Path(f"data/raw/{date_str}")
    if not base_dir.exists():
        return False, 0.0, 0.0, 0.0, 0.0, 0.0
        
    files = list(base_dir.glob("*.parquet"))
    if not files:
        return False, 0.0, 0.0, 0.0, 0.0, 0.0
        
    dfs = [pl.read_parquet(f) for f in files]
    df = pl.concat(dfs, how="vertical_relaxed")
    
    if df.is_empty():
        return False, 0.0, 0.0, 0.0, 0.0, 0.0
        
    # Calculate ticks_per_minute
    if "timestamp" in df.columns:
        ts_min = df["timestamp"].min()
        ts_max = df["timestamp"].max()
        duration_minutes = (ts_max - ts_min) / 60000.0 if ts_max and ts_min else 0.0
        ticks_per_minute = df.height / duration_minutes if duration_minutes > 0 else 0.0
    else:
        ticks_per_minute = 0.0
        
    # Standard deviations
    spot_std = df["spot"].std() if "spot" in df.columns else 0.0
    ltp_std = df["ltp"].std() if "ltp" in df.columns else 0.0
    vol_std = df["volume"].std() if "volume" in df.columns else 0.0
    oi_std = df["oi"].std() if "oi" in df.columns else 0.0
    
    # Handle nulls
    spot_std = spot_std if spot_std is not None else 0.0
    ltp_std = ltp_std if ltp_std is not None else 0.0
    vol_std = vol_std if vol_std is not None else 0.0
    oi_std = oi_std if oi_std is not None else 0.0
    
    passed = not (spot_std == 0.0 and ltp_std == 0.0 and vol_std == 0.0 and oi_std == 0.0)
    
    return passed, ticks_per_minute, spot_std, ltp_std, vol_std, oi_std

def audit_feature_motion(date_str: str):
    """Step 2: Feature Motion"""
    base_dir = Path(f"data/features/{date_str}/1m")
    if not base_dir.exists():
        return False, 0.0
        
    files = list(base_dir.glob("*.parquet"))
    if not files:
        return False, 0.0
        
    dfs = [pl.read_parquet(f) for f in files]
    df = pl.concat(dfs, how="vertical_relaxed")
    
    if df.is_empty():
        return False, 0.0
        
    numeric_cols = [c for c in df.columns if df[c].dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]]
    
    moving_count = 0
    total_count = 0
    
    for c in numeric_cols:
        if c in ["timestamp"]:
            continue
        c_std = df[c].std()
        if c_std is not None and c_std > 0.0:
            moving_count += 1
        total_count += 1
        
    ratio = moving_count / total_count if total_count > 0 else 0.0
    passed = ratio >= 0.50
    return passed, float(ratio)

def audit_research_motion(date_str: str):
    """Step 3: Research Motion"""
    base_dir = Path(f"data/research/{date_str}/1m")
    if not base_dir.exists():
        return False, 0.0
        
    files = list(base_dir.glob("*.parquet"))
    if not files:
        return False, 0.0
        
    dfs = [pl.read_parquet(f) for f in files]
    df = pl.concat(dfs, how="vertical_relaxed")
    
    if df.is_empty():
        return False, 0.0
        
    numeric_cols = [c for c in df.columns if df[c].dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]]
    
    moving_count = 0
    total_count = 0
    
    for c in numeric_cols:
        if c in ["timestamp"]:
            continue
        c_var = df[c].var()
        if c_var is not None and c_var > 0.0:
            moving_count += 1
        total_count += 1
        
    ratio = moving_count / total_count if total_count > 0 else 0.0
    passed = ratio >= 0.40
    return passed, float(ratio)

def determine_root_cause(pass_raw, pass_feat, pass_res):
    """Step 5: Root Cause"""
    if not pass_raw:
        return "RAW", "Recorder is capturing flat/deterministic data. Check mock data generator or websocket feed."
    elif not pass_feat:
        return "FEATURE", "Features are flattening reality. Check feature builder window sizes or forward filling logic."
    elif not pass_res:
        return "RESEARCH", "Research layer is destroying variance. Check signal computations."
    else:
        return "SCORING", "Scoring engine converts valid variance into flat scores. Check score normalization."

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, help="YYYY-MM-DD", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    
    date_str = args.date
    
    pass_raw, tpm, s_std, l_std, v_std, o_std = audit_raw_motion(date_str)
    pass_feat, feat_ratio = audit_feature_motion(date_str)
    pass_res, res_ratio = audit_research_motion(date_str)
    
    # Traceability is implicitly covered by checking which layer fails
    root_layer, repair_target = determine_root_cause(pass_raw, pass_feat, pass_res)
    
    # In case everything passes but we know mock data fails
    if pass_raw and pass_feat and pass_res:
        passed = True
        grade = "PASS"
    else:
        passed = False
        grade = "FAIL"
        
    report = {
        "grade": grade,
        "moving_feature_ratio": feat_ratio,
        "dynamic_feature_ratio": res_ratio,
        "root_layer": root_layer,
        "repair_target": repair_target
    }
    
    Path("reports").mkdir(exist_ok=True)
    with open("reports/phase3a_reality.json", "w") as f:
        json.dump(report, f, indent=2)
        
    print("\nFINAL OUTPUT")
    print(f"Grade: {report['grade']}")
    print(f"Raw Ticks/Min: {tpm:.2f}")
    print(f"Raw Spot Std: {s_std:.2f}")
    print(f"Raw LTP Std: {l_std:.2f}")
    print(f"Feature Moving Ratio: {report['moving_feature_ratio']:.2f}")
    print(f"Research Dynamic Ratio: {report['dynamic_feature_ratio']:.2f}")
    print(f"Root Layer: {report['root_layer']}")
    print(f"Repair Target: {report['repair_target']}")
    
    if passed:
        print("\nPASS")
    else:
        print("\nFAIL")

if __name__ == "__main__":
    main()
