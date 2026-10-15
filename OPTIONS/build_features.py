import argparse
import sys
from datetime import datetime

from features.builder import build_features
from features.quality import run_quality_gate
from features.schema import validate_schema

def main():
    parser = argparse.ArgumentParser(description="Build features for Phase 2")
    parser.add_argument("--date", type=str, help="Date in YYYY-MM-DD format (defaults to today)")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild features even if they exist")
    parser.add_argument("--dry-run", action="store_true", help="Dry run, do not write to disk")
    args = parser.parse_args()

    target_date = args.date if args.date else datetime.now().strftime("%Y-%m-%d")
    
    print(f"Building features for {target_date} (dry_run={args.dry_run})")
    
    res = build_features(target_date, dry_run=args.dry_run)
    
    df_features = res.get("df_features")
    if df_features is not None and not df_features.is_empty():
        validate_schema(df_features)
        
    quality_report = run_quality_gate(df_features, res.get("rows_loaded", 0))

    print("\nFINAL OUTPUT")
    print(f"Rows Loaded: {res['rows_loaded']}")
    print(f"Rows Produced: {res['rows_output']}")
    
    # Feature count refers to columns count? Or df height? The prompt says "Feature Count". 
    # Maybe columns count? Schema has 22 columns. Or number of feature bars?
    # Let's say it's df_features.width
    feature_count = df_features.width if df_features is not None else 0
    print(f"Feature Count: {feature_count}")
    print(f"Quality Score: {quality_report['score']}")

    # PASS IF:
    # feature_rows > 1000
    # duplicate_rate < 0.5%
    # null_rate < 1%
    # runtime < 5 min
    feature_rows = df_features.height if df_features is not None else 0
    dup_rate = quality_report.get("duplicate_rate", 0.0)
    null_rate = quality_report.get("null_rate", 0.0)
    runtime = res["build_time"]
    
    passed = (
        feature_rows > 1000 and
        dup_rate < 0.005 and
        null_rate < 0.01 and
        runtime < 300
    )

    if passed:
        print("PASS")
        print("PHASE 2A COMPLETE")
    else:
        print("FAIL")
        print("Reasons:")
        if feature_rows <= 1000:
            print(f" - feature_rows = {feature_rows} (needs > 1000)")
        if dup_rate >= 0.005:
            print(f" - duplicate_rate = {dup_rate:.2%} (needs < 0.5%)")
        if null_rate >= 0.01:
            print(f" - null_rate = {null_rate:.2%} (needs < 1%)")
        if runtime >= 300:
            print(f" - runtime = {runtime:.2f}s (needs < 300s)")

if __name__ == "__main__":
    main()
