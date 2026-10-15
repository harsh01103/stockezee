import base64
import polars as pl
from pathlib import Path
import os
import glob
from google.protobuf.json_format import MessageToJson

from market.proto import MarketDataFeed_pb2 as pb

def dump_json():
    event_dirs = sorted(Path("data/events").glob("2026-*"))
    if not event_dirs: return
    latest_dir = event_dirs[-1]
    files = list(latest_dir.glob("*.parquet"))
    files.sort(key=os.path.getmtime)
    
    df = pl.read_parquet(files[-1])
    for row in df.head(2).iter_rows(named=True):
        payload_b64 = row.get("payload")
        if not payload_b64: continue
        payload = base64.b64decode(payload_b64)
        feed_response = pb.FeedResponse()
        feed_response.ParseFromString(payload)
        
        print(MessageToJson(feed_response, preserving_proto_field_name=True))

if __name__ == "__main__":
    dump_json()
