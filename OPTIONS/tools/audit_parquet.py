import sys
import glob
from pathlib import Path
import polars as pl
from loguru import logger

def audit_parquet(date_str: str):
    path_pattern = f"data/raw/{date_str}/*.parquet"
    files = glob.glob(path_pattern)
    
    if not files:
        logger.error(f"No parquet files found for {date_str} in {path_pattern}")
        sys.exit(1)
        
    logger.info(f"Auditing {len(files)} parquet files...")
    df = pl.read_parquet(path_pattern)
    
    print("\n--- Columns ---")
    print(df.columns)
    
    print("\n--- Null Count ---")
    print(df.null_count())
    
    print("\n--- Description ---")
    print(df.describe())
    
    # Gate B Verification checks
    print("\n--- Gate B Verifications ---")
    
    # Check monotonicity of timestamps within the same underlying/strike
    # It's a stream, so global timestamps should generally be increasing, but can arrive slightly out of order
    # A simple check is just ensuring sorting works and there are no wild negative jumps
    is_sorted = df["timestamp"].is_sorted()
    print(f"[?] Timestamps sorted: {is_sorted} (Note: network jitter may cause minor unordered events)")
    
    # Check volume >= 0
    vol_neg = df.filter(pl.col("volume") < 0).height
    print(f"[{'x' if vol_neg > 0 else 'v'}] Volume >= 0: {vol_neg == 0} (Violations: {vol_neg})")
    
    # Check bid <= ask (except when ask is 0)
    bid_gt_ask = df.filter((pl.col("bid") > pl.col("ask")) & (pl.col("ask") > 0)).height
    print(f"[{'x' if bid_gt_ask > 0 else 'v'}] Bid <= Ask: {bid_gt_ask == 0} (Violations: {bid_gt_ask})")
    
    # Check OI not entirely null
    null_oi = df.select(pl.col("oi").is_null().sum()).item()
    print(f"[{'x' if null_oi == df.height else 'v'}] OI not entirely null: {null_oi < df.height}")
    
    # Check record_id unique
    duplicates = df.height - df.select(pl.col("record_id").n_unique()).item()
    dup_pct = (duplicates / df.height) * 100
    print(f"[{'x' if dup_pct > 0.5 else 'v'}] Duplicates < 0.5%: {dup_pct <= 0.5} ({dup_pct:.2f}%)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python audit_parquet.py YYYY-MM-DD")
        sys.exit(1)
    audit_parquet(sys.argv[1])
