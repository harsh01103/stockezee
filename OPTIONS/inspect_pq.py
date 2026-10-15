import polars as pl
from pathlib import Path

files = list(Path(f"data/raw/2026-06-25").glob("*.parquet"))
if files:
    df = pl.read_parquet(files[-1])
    print("Columns:", sorted(df.columns))
else:
    print("No parquet files found")
