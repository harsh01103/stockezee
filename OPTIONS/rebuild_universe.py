import argparse
import sys
from datetime import datetime
from pathlib import Path
import polars as pl
import json

from opportunities.universe import build_universe

def trace_loss(date_str: str):
    """Step 1: Trace Loss"""
    stages = [
        ("raw", f"data/raw/{date_str}"),
        ("features", f"data/features/{date_str}/1m"),
        ("research", f"data/research/{date_str}/1m"),
        ("signals", f"data/signals/{date_str}/1m"),
        ("opportunities", f"data/opportunities/{date_str}/1m")
    ]
    
    Path("reports").mkdir(exist_ok=True)
    with open("reports/lineage.csv", "w") as f:
        f.write("stage,rows,unique_timestamps,unique_strikes\n")
        
        for stage_name, path_str in stages:
            p = Path(path_str)
            if not p.exists():
                f.write(f"{stage_name},0,0,0\n")
                continue
                
            files = list(p.glob("*.parquet"))
            if not files:
                f.write(f"{stage_name},0,0,0\n")
                continue
                
            dfs = [pl.read_parquet(fp) for fp in files]
            df = pl.concat(dfs, how="vertical_relaxed")
            
            rows = df.height
            unique_ts = df["timestamp"].n_unique() if "timestamp" in df.columns else 0
            unique_strikes = df["strike"].n_unique() if "strike" in df.columns else 0
            
            f.write(f"{stage_name},{rows},{unique_ts},{unique_strikes}\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, help="YYYY-MM-DD", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    
    date_str = args.date
    base_dir = Path(f"data/signals/{date_str}")
    
    if not base_dir.exists():
        print(f"No signals data found for {date_str}")
        sys.exit(1)
        
    trace_loss(date_str)
    
    interval_dir = base_dir / "1m"
    if not interval_dir.exists():
        print("No 1m data found")
        sys.exit(1)
        
    files = list(interval_dir.glob("*.parquet"))
    dfs = [pl.read_parquet(f) for f in files]
    df = pl.concat(dfs, how="vertical_relaxed")
    
    print(f"Loaded {df.height} signal rows for rebuilding.")
    
    # Rebuild Candidate Expansion directly via repaired universe.py
    df_uni = build_universe(df)
    
    # Identity Preservation Check
    missing_identities = False
    req_fields = ["instrument_key", "underlying", "expiry", "strike", "option_type"]
    for f in req_fields:
        if f not in df_uni.columns:
            missing_identities = True
            break
            
        if df_uni[f].null_count() > 0:
            missing_identities = True
            break
            
        if df_uni[f].dtype == pl.Utf8:
            if df_uni.filter((pl.col(f) == "UNKNOWN") | (pl.col(f) == "NULL")).height > 0:
                missing_identities = True
                break
                
        if f == "strike":
            if df_uni.filter(pl.col(f) == 0.0).height > 0:
                missing_identities = True
                break
                
    # Cross section audit
    counts = df_uni.group_by("timestamp").agg(pl.len().alias("count"))
    if counts.is_empty():
        min_c, median_c, max_c = 0, 0, 0
    else:
        min_c = counts["count"].min()
        median_c = counts["count"].median()
        max_c = counts["count"].max()
        
    # Duplicate check
    duplicate_ratio = 0.0
    if not df_uni.is_empty():
        dup_count = df_uni.height - df_uni.select(["timestamp", "instrument_key"]).unique().height
        duplicate_ratio = dup_count / df_uni.height
        
    passed = (not missing_identities) and (median_c >= 20)
    
    grade = "PASS" if passed else "FAIL"
    
    report = {
        "grade": grade,
        "identity_preserved": not missing_identities,
        "cross_section_score": float(median_c),
        "median_candidates": float(median_c),
        "duplicate_ratio": float(duplicate_ratio)
    }
    
    Path("reports").mkdir(exist_ok=True)
    with open("reports/phase3a_universe.json", "w") as f:
        json.dump(report, f, indent=2)
        
    print("\nFINAL OUTPUT")
    print(f"Grade: {report['grade']}")
    print(f"Identity Preserved: {report['identity_preserved']}")
    print(f"Median Candidates: {report['median_candidates']}")
    
    if passed:
        # We also need to save this repaired universe so that later stages can use it.
        # But wait, scoring relies on the output of universe.
        # The prompt says "Only rebuild: opportunities" and "Do not rerun scoring."
        # This implies we just report the universe output. 
        print("\nPASS")
        print("PHASE 3A.2 COMPLETE")
    else:
        print("\nFAIL")

if __name__ == "__main__":
    main()
