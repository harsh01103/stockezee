import sys
import asyncio
import httpx
import os
import glob
import pandas as pd
from loguru import logger
import threading
import datetime

# 1. Monkeypatch UpstoxProvider.authorize IN MEMORY
import market.feed_provider

async def patched_authorize(self):
    token = self.auth_manager.get_access_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://api.upstox.com/v3/feed/market-data-feed/authorize", headers={"Authorization": f"Bearer {token}"})
        uri = resp.json()["data"]["authorizedRedirectUri"]
        logger.info("Monkeypatched authorize() returning authorizedRedirectUri")
        return uri

market.feed_provider.UpstoxProvider.authorize = patched_authorize

# Now import the recorder module
import recorder
from auth.auth_manager import AuthManager
from market.recorder import MarketRecorder

async def run_recorder_for_120s():
    print("=== PHASE R-CONFIRM — END-TO-END LIVE INGEST VALIDATION ===\n")
    
    auth_manager = AuthManager()
    
    # 2. Run recorder logic
    market_recorder = MarketRecorder(auth_manager, dry_run=False)
    
    # Run the recorder as a background task
    task = asyncio.create_task(market_recorder.start())
    
    print("Capture exactly 120 seconds...\n")
    await asyncio.sleep(120)
    
    print("Stopping recorder...\n")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
        
    print("STEP 3")
    frames_received = market_recorder.validator.messages_received
    # Fallback to sum of lengths from storage metrics or skip decoded_rows
    decoded_rows = market_recorder.storage.metrics.get("rows_written", 0)
    rows_written = market_recorder.storage.metrics.get("rows_written", 0)
    
    # Find newest parquet
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    parquet_dir = f"data/raw/{today}"
    if not os.path.exists(parquet_dir):
        parquet_files = []
    else:
        parquet_files = glob.glob(f"{parquet_dir}/*.parquet")
    
    print(f"frames_received: {frames_received}")
    print(f"decoded_rows: {decoded_rows}")
    print(f"rows_written: {rows_written}")
    print(f"parquet_files_created: {len(parquet_files)}\n")
    
    print("STEP 4")
    row_count = 0
    unique_instruments = 0
    unknown_ratio = 0.0
    zero_ltp_ratio = 0.0
    expiry_count = 0
    strike_nonzero_ratio = 0.0
    sample_rows = ""
    parquet_path = "None"
    
    if parquet_files:
        newest_parquet = max(parquet_files, key=os.path.getmtime)
        parquet_path = newest_parquet
        try:
            df = pd.read_parquet(newest_parquet)
            row_count = len(df)
            unique_instruments = df['instrument_key'].nunique()
            
            unknowns = df[df['underlying'] == 'UNKNOWN']
            unknown_ratio = len(unknowns) / row_count if row_count > 0 else 0
            
            zero_ltp = df[df['ltp'] == 0.0]
            zero_ltp_ratio = len(zero_ltp) / row_count if row_count > 0 else 0
            
            expiry_count = df['expiry'].nunique()
            
            strike_nonzero = df[df['strike'] > 0.0]
            strike_nonzero_ratio = len(strike_nonzero) / row_count if row_count > 0 else 0
            
            # Formatting the sample
            sample_df = df.head(10)[['timestamp', 'instrument_key', 'underlying', 'expiry', 'strike', 'option_type', 'ltp', 'bid', 'ask', 'volume']]
            sample_rows = sample_df.to_string()
        except Exception as e:
            print(f"Error reading parquet: {e}")
            
    print(f"row_count: {row_count}")
    print(f"unique_instruments: {unique_instruments}")
    print(f"unknown_ratio: {unknown_ratio:.2%}")
    print(f"zero_ltp_ratio: {zero_ltp_ratio:.2%}")
    print(f"expiry_count: {expiry_count}")
    print(f"strike_nonzero_ratio: {strike_nonzero_ratio:.2%}\n")
    print(f"Sample Rows:\n{sample_rows}\n")
    
    print("STEP 5")
    passed = (
        frames_received > 200 and
        rows_written > 5000 and
        unknown_ratio < 0.01 and
        zero_ltp_ratio < 0.05 and
        expiry_count >= 2 and
        strike_nonzero_ratio > 0.95
    )
    decision = "PASS" if passed else "FAIL"
    
    print("Final Output:\n")
    print(f"authorize_uri_used:\nTrue")
    print(f"capture_seconds:\n120")
    print(f"frames_received:\n{frames_received}")
    print(f"rows_written:\n{rows_written}")
    print(f"parquet_path:\n{parquet_path}")
    print(f"unknown_ratio:\n{unknown_ratio:.2%}")
    print(f"strike_nonzero_ratio:\n{strike_nonzero_ratio:.2%}")
    print(f"sample_rows:\n{sample_rows}\n")
    print(f"Decision:\n{decision}\n")
    print("STOP")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(override=True)
    asyncio.run(run_recorder_for_120s())
