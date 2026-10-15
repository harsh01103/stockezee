import polars as pl
from pathlib import Path
import glob
import os

def analyze_forensics():
    # Find latest parquet directory
    raw_dirs = sorted(Path("data/raw").glob("2026-*"))
    if not raw_dirs:
        print("No raw data found")
        return
        
    latest_dir = raw_dirs[-1]
    files = list(latest_dir.glob("*.parquet"))
    if not files:
        print("No parquet files")
        return
        
    # Sort files by modification time
    files.sort(key=os.path.getmtime)
    
    # Let's just read the last file to see recent data
    df = pl.read_parquet(files[-1])
    
    print("=== STEP 1: RAW VALUE INSPECTION ===")
    cols = ["timestamp", "instrument_key", "ltp", "bid", "ask", "volume", "oi", "source_type", "feed_type"]
    avail_cols = [c for c in cols if c in df.columns]
    
    df_500 = df.head(500)

    
    for c in ["ltp", "bid", "ask", "volume", "oi"]:
        if c not in df.columns: continue
        
        non_null = df[c].is_not_null().sum()
        non_null_ratio = non_null / df.height if df.height > 0 else 0
        
        zero_ratio = (df[c] == 0).sum() / df.height if df.height > 0 else 0
        
        distinct = df[c].n_unique()
        std = df[c].std()
        cmin = df[c].min()
        cmax = df[c].max()
        
        print(f"\n{c.upper()}:")
        print(f"  non_null_ratio: {non_null_ratio:.2f}")
        print(f"  zero_ratio:     {zero_ratio:.2f}")
        print(f"  distinct_count: {distinct}")
        print(f"  stddev:         {std}")
        print(f"  min:            {cmin}")
        print(f"  max:            {cmax}")

    print("\n=== STEP 3: PARTIAL FEED AUDIT ===")
    if "feed_type" in df.columns:
        feed_counts = df["feed_type"].value_counts()
        print(feed_counts)
        
    print("\n=== STEP 4: LOOKUP COMPLETENESS ===")
    if "underlying" in df.columns:
        unresolved = df.filter(pl.col("underlying") == "UNKNOWN")
        if not unresolved.is_empty():
            print(unresolved.group_by("instrument_key").count())

if __name__ == "__main__":
    analyze_forensics()
