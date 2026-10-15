import base64
import polars as pl
from pathlib import Path
import glob
import os

from market.proto import MarketDataFeed_pb2 as pb

def find_nonzero_bp():
    event_dirs = sorted(Path("data/events").glob("2026-*"))
    if not event_dirs: return
    latest_dir = event_dirs[-1]
    files = list(latest_dir.glob("*.parquet"))
    files.sort(key=os.path.getmtime)
    
    dfs = [pl.read_parquet(f) for f in files[-10:]]
    df = pl.concat(dfs, how="diagonal_relaxed")
    
    found_bp = 0
    found_ltp = 0
    
    for row in df.iter_rows(named=True):
        payload_b64 = row.get("payload")
        if not payload_b64: continue
        payload = base64.b64decode(payload_b64)
        feed_response = pb.FeedResponse()
        feed_response.ParseFromString(payload)
        
        for key, feed in feed_response.feeds.items():
            if feed.HasField("fullFeed"):
                ff = feed.fullFeed
                if ff.ltp > 0: found_ltp += 1
                if ff.HasField("marketLevel") and len(ff.marketLevel.bidAskQuote) > 0:
                    if ff.marketLevel.bidAskQuote[0].bp > 0:
                        found_bp += 1
                        
    print(f"Total events: {df.height}")
    print(f"Payloads with ltp > 0: {found_ltp}")
    print(f"Payloads with bp > 0: {found_bp}")

if __name__ == "__main__":
    find_nonzero_bp()
