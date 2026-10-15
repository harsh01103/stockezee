import polars as pl
import glob
import hashlib
from datetime import datetime

def inspect_raw():
    files = glob.glob("data/raw/2026-06-17/*.parquet")
    for f in files[:5]: # just top 5 for now
        df = pl.read_parquet(f)
        row_count = df.height
        with open(f, "rb") as file_bytes:
            h = hashlib.sha256(file_bytes.read()).hexdigest()
        
        min_ts = df["timestamp"].min()
        max_ts = df["timestamp"].max()
        
        # print 1, 2
        print(f"source_file: {f}")
        print(f"row_count: {row_count}")
        print(f"sha256: {h}")
        print(f"min_timestamp: {min_ts}")
        print(f"max_timestamp: {max_ts}")
        
        try:
            dt_min = datetime.fromtimestamp(min_ts / 1000)
            dt_max = datetime.fromtimestamp(max_ts / 1000)
            print(f"Dates: {dt_min} to {dt_max}")
        except:
            print("Invalid timestamps")

if __name__ == "__main__":
    inspect_raw()
