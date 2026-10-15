import json
import polars as pl
from pathlib import Path
from loguru import logger

def run_quality_gate(df: pl.DataFrame, raw_rows: int) -> dict:
    """
    Runs quality checks on the generated features dataset.
    Reject if:
    - null >1%
    - duplicate >0.5% (duplicates are measured relative to raw rows or the df itself if pre-deduplicated)
    - missing timestamps
    - negative volume
    """
    total_rows = df.height
    if total_rows == 0:
        return {"passed": False, "reason": "Empty dataset"}
        
    # Check nulls
    null_count = df.null_count().sum_horizontal()[0]
    null_rate = null_count / (total_rows * df.width)
    
    # Check duplicates (assuming duplicates have exactly same primary keys)
    pk_cols = ["timestamp", "underlying", "expiry", "strike", "option_type"]
    unique_rows = df.select(pk_cols).unique().height
    duplicate_rate = (total_rows - unique_rows) / max(total_rows, 1)
    
    # Check missing timestamps
    missing_timestamps = df.filter(pl.col("timestamp").is_null()).height
    
    # Check negative volume
    negative_volume = df.filter(pl.col("volume") < 0).height
    
    passed = True
    reasons = []
    
    if null_rate > 0.01:
        passed = False
        reasons.append(f"Null rate > 1% ({null_rate:.2%})")
        
    if duplicate_rate > 0.005:
        passed = False
        reasons.append(f"Duplicate rate > 0.5% ({duplicate_rate:.2%})")
        
    if missing_timestamps > 0:
        passed = False
        reasons.append(f"Missing timestamps: {missing_timestamps} rows")
        
    if negative_volume > 0:
        passed = False
        reasons.append(f"Negative volume: {negative_volume} rows")
        
    score = 100
    if not passed:
        score -= len(reasons) * 20
        
    report = {
        "passed": passed,
        "score": max(0, score),
        "total_rows": total_rows,
        "null_rate": null_rate,
        "duplicate_rate": duplicate_rate,
        "missing_timestamps": missing_timestamps,
        "negative_volume": negative_volume,
        "reasons": reasons
    }
    
    Path("reports").mkdir(exist_ok=True)
    with open("reports/feature_quality.json", "w") as f:
        json.dump(report, f, indent=2)
        
    return report
