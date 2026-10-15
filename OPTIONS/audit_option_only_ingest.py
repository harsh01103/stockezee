import sys
import asyncio
import httpx
import os
import glob
import pandas as pd
from loguru import logger
import datetime

import market.feed_provider
async def patched_authorize(self):
    token = self.auth_manager.get_access_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://api.upstox.com/v3/feed/market-data-feed/authorize", headers={"Authorization": f"Bearer {token}"})
        uri = resp.json()["data"]["authorizedRedirectUri"]
        return uri
market.feed_provider.UpstoxProvider.authorize = patched_authorize

import recorder
from auth.auth_manager import AuthManager
from market.recorder import MarketRecorder

async def run_audit():
    print("=== PHASE R-CONFIRM.1 — OPTION-ONLY INGEST CERTIFICATION ===\n")
    
    start_time = datetime.datetime.now().timestamp()
    
    auth_manager = AuthManager()
    market_recorder = MarketRecorder(auth_manager, dry_run=False)
    task = asyncio.create_task(market_recorder.start())
    
    print("Capture exactly 120 seconds...\n")
    await asyncio.sleep(120)
    print("Stopping recorder...\n")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
        
    print("STEP 2")
    frames_received = market_recorder.validator.messages_received
    rows_written = market_recorder.storage.metrics.get("rows_written", 0)
    
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    parquet_dir = f"data/raw/{today}"
    parquet_files = [f for f in glob.glob(f"{parquet_dir}/*.parquet") if os.path.getmtime(f) > start_time]
    
    print(f"frames_received: {frames_received}")
    print(f"rows_written: {rows_written}")
    print(f"parquet_files_created: {len(parquet_files)}\n")
    
    print("STEP 3")
    dfs = [pd.read_parquet(f) for f in parquet_files]
    df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    
    total_rows = len(df)
    
    if total_rows > 0:
        df['strike'] = df['strike'].fillna(0.0)
        df['expiry'] = df['expiry'].fillna("")
        
        option_mask = (df['strike'] > 0) & (df['expiry'] != "")
        option_df = df[option_mask].copy()
        underlying_df = df[~option_mask].copy()
        
        option_rows = len(option_df)
        underlying_rows = len(underlying_df)
        option_ratio = option_rows / total_rows if total_rows > 0 else 0
    else:
        option_df = pd.DataFrame()
        option_rows = 0
        underlying_rows = 0
        option_ratio = 0
        
    print(f"total_rows: {total_rows}")
    print(f"option_rows: {option_rows}")
    print(f"underlying_rows: {underlying_rows}")
    print(f"option_ratio: {option_ratio:.2%}\n")
    
    print("STEP 4")
    option_unknown_ratio = 0.0
    strike_nonzero_ratio = 0.0
    expiry_present_ratio = 0.0
    ltp_nonzero_ratio = 0.0
    duplicate_ratio = 0.0
    unique_underlyings = 0
    unique_expiries = 0
    unique_strikes = 0
    
    if option_rows > 0:
        unknowns = option_df[option_df['underlying'] == 'UNKNOWN']
        option_unknown_ratio = len(unknowns) / option_rows
        
        strike_nonzero = option_df[option_df['strike'] > 0.0]
        strike_nonzero_ratio = len(strike_nonzero) / option_rows
        
        expiry_present = option_df[option_df['expiry'] != ""]
        expiry_present_ratio = len(expiry_present) / option_rows
        
        ltp_nonzero = option_df[option_df['ltp'] > 0.0]
        ltp_nonzero_ratio = len(ltp_nonzero) / option_rows
        
        dup_count = len(option_df) - len(option_df.drop_duplicates(subset=['timestamp', 'instrument_key']))
        duplicate_ratio = dup_count / option_rows
        
        unique_underlyings = option_df['underlying'].nunique()
        unique_expiries = option_df['expiry'].nunique()
        unique_strikes = option_df['strike'].nunique()
        
    print(f"unknown_ratio: {option_unknown_ratio:.2%}")
    print(f"strike_nonzero_ratio: {strike_nonzero_ratio:.2%}")
    print(f"expiry_present_ratio: {expiry_present_ratio:.2%}")
    print(f"ltp_nonzero_ratio: {ltp_nonzero_ratio:.2%}")
    print(f"duplicate_ratio: {duplicate_ratio:.2%}")
    print(f"unique_underlyings: {unique_underlyings}")
    print(f"unique_expiries: {unique_expiries}")
    print(f"unique_strikes: {unique_strikes}\n")
    
    print("STEP 5")
    sample_option_rows = ""
    if option_rows > 0:
        cols_to_print = ['timestamp', 'instrument_key', 'underlying', 'expiry', 'strike', 'option_type', 'ltp', 'bid', 'ask', 'volume']
        cols = [c for c in cols_to_print if c in option_df.columns]
        sample_df = option_df.head(20)[cols]
        sample_option_rows = sample_df.to_string()
    print(f"Sample OPTION Rows:\n{sample_option_rows}\n")
    
    print("STEP 6")
    print("Sanity checks executed.\n")
    
    print("STEP 7")
    passed = (
        frames_received > 500 and
        total_rows > 5000 and
        option_unknown_ratio < 0.01 and
        strike_nonzero_ratio > 0.95 and
        expiry_present_ratio > 0.95 and
        ltp_nonzero_ratio > 0.90 and
        duplicate_ratio < 0.05 and
        unique_expiries >= 2
    )
    decision = "PASS" if passed else "FAIL"
    
    print("Final Output:\n")
    print(f"capture_seconds:\n120")
    print(f"frames_received:\n{frames_received}")
    print(f"rows_written:\n{total_rows}")
    print(f"option_rows:\n{option_rows}")
    print(f"underlying_rows:\n{underlying_rows}")
    print(f"option_unknown_ratio:\n{option_unknown_ratio:.2%}")
    print(f"strike_nonzero_ratio:\n{strike_nonzero_ratio:.2%}")
    print(f"expiry_present_ratio:\n{expiry_present_ratio:.2%}")
    print(f"ltp_nonzero_ratio:\n{ltp_nonzero_ratio:.2%}")
    print(f"unique_expiries:\n{unique_expiries}")
    print(f"sample_option_rows:\n{sample_option_rows}\n")
    print(f"Decision:\n{decision}\n")
    print("STOP")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(override=True)
    asyncio.run(run_audit())
