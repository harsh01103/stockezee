import polars as pl
from pathlib import Path
import os
import json

def find_missing():
    raw_dirs = sorted(Path("data/raw").glob("2026-*"))
    if not raw_dirs: return
    latest_dir = raw_dirs[-1]
    files = list(latest_dir.glob("*.parquet"))
    files.sort(key=os.path.getmtime)
    
    dfs = []
    for f in files[-10:]:
        dfs.append(pl.read_parquet(f))
    df = pl.concat(dfs, how="diagonal_relaxed")
    
    unresolved = df.filter(pl.col("underlying") == "UNKNOWN")
    if unresolved.is_empty():
        print("No UNKNOWN underlying found.")
    else:
        counts = unresolved.group_by("instrument_key").count().sort("count", descending=True)
        print("Missing instruments:")
        print(counts)

if __name__ == "__main__":
    find_missing()
