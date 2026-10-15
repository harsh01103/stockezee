import argparse
import sys
from datetime import datetime
from pathlib import Path
import polars as pl

from trade.constructor import build_trade_candidates

def main():
    parser = argparse.ArgumentParser(description="Build Trade Candidates (Phase 3B)")
    parser.add_argument("--date", type=str, help="YYYY-MM-DD", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()

    date_str = args.date
    opps_dir = Path(f"data/opportunities/{date_str}")
    
    if not opps_dir.exists():
        print(f"No opportunities found for {date_str}")
        sys.exit(1)

    print(f"Building trade candidates for {date_str}")
    
    rows_in = 0
    rows_out = 0
    
    # We will process each interval if they exist
    for interval in ["1m", "5m", "15m"]:
        interval_dir = opps_dir / interval
        if not interval_dir.exists():
            continue
            
        files = list(interval_dir.glob("*.parquet"))
        if not files:
            continue
            
        dfs = [pl.read_parquet(f) for f in files]
        df_opps = pl.concat(dfs, how="diagonal_relaxed")
        
        rows_in += df_opps.height
        
        df_trades = build_trade_candidates(df_opps)
        rows_out += df_trades.height
        
        if df_trades.height > 0:
            out_dir = Path(f"data/trades/{date_str}/{interval}")
            out_dir.mkdir(parents=True, exist_ok=True)
            df_trades.write_parquet(out_dir / f"trades_{date_str}.parquet")

    print("\nFINAL OUTPUT")
    print(f"Opportunities Read: {rows_in}")
    print(f"Trades Built: {rows_out}")
    print("PHASE 3B BUILD COMPLETE")

if __name__ == "__main__":
    main()
