import base64
import polars as pl
from pathlib import Path
import os
import glob
from google.protobuf.json_format import MessageToJson

from market.proto import MarketDataFeed_pb2 as pb

def find_initial_feed():
    event_dirs = sorted(Path("data/events").glob("2026-*"))
    if not event_dirs: return
    latest_dir = event_dirs[-1]
    files = list(latest_dir.glob("*.parquet"))
    files.sort(key=os.path.getmtime)
    
    found_initial = False
    
    # Read the first file generated in the session
    for f in files[:2]:
        df = pl.read_parquet(f)
        for row in df.iter_rows(named=True):
            payload_b64 = row.get("payload")
            if not payload_b64: continue
            payload = base64.b64decode(payload_b64)
            feed_response = pb.FeedResponse()
            feed_response.ParseFromString(payload)
            
            if feed_response.type == pb.FeedResponse.initial_feed:
                print("FOUND INITIAL FEED!")
                print(MessageToJson(feed_response, preserving_proto_field_name=True))
                found_initial = True
                break
        if found_initial:
            break
            
    if not found_initial:
        print("No initial_feed found in the first two event files.")

if __name__ == "__main__":
    find_initial_feed()
