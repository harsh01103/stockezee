import base64
import polars as pl
from pathlib import Path
import glob
import os

from market.proto import MarketDataFeed_pb2 as pb
from market.decoder import FeedType

def trace_protobuf():
    event_dirs = sorted(Path("data/events").glob("2026-*"))
    if not event_dirs:
        print("No events found.")
        return
        
    latest_dir = event_dirs[-1]
    files = list(latest_dir.glob("*.parquet"))
    if not files:
        print("No event parquet files found.")
        return
        
    files.sort(key=os.path.getmtime)
    
    dfs = []
    for f in files[-10:]:
        dfs.append(pl.read_parquet(f))
        
    df = pl.concat(dfs, how="diagonal_relaxed")
    
    if df.is_empty():
        print("Empty events dataframe.")
        return
        
    print(f"Total events in file: {df.height}")
    
    parsed = 0
    # Process up to 50 payloads
    for i, row in enumerate(df.iter_rows(named=True)):
        payload_b64 = row.get("payload")
        if not payload_b64:
            continue
            
        payload = base64.b64decode(payload_b64)
        feed_response = pb.FeedResponse()
        feed_response.ParseFromString(payload)
        
        for instrument_key, feed in feed_response.feeds.items():
            parsed += 1
            if parsed > 50:
                return
            print(f"\nMessage {i} | Instrument: {instrument_key}")
            print(feed)
                


if __name__ == "__main__":
    trace_protobuf()
