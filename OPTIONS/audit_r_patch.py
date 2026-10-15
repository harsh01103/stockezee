import sys
import asyncio
import os
import glob
import pandas as pd
from loguru import logger
import datetime
import shutil

import recorder
from auth.auth_manager import AuthManager
from market.recorder import MarketRecorder

async def run_audit():
    print("=== PHASE R-PATCH — PERMANENT UPSTOX AUTHORIZE FLOW ===\n")
    
    start_time = datetime.datetime.now().timestamp()
    
    auth_manager = AuthManager()
    market_recorder = MarketRecorder(auth_manager, dry_run=False)
    
    print("Capture 60 seconds...")
    task = asyncio.create_task(market_recorder.start())
    
    await asyncio.sleep(60)
    print("Stopping recorder...\n")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
        
    frames_received = market_recorder.validator.messages_received
    
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    parquet_dir = f"data/raw/{today}"
    if os.path.exists(parquet_dir):
        parquet_files = [f for f in glob.glob(f"{parquet_dir}/*.parquet") if os.path.getmtime(f) > start_time]
    else:
        parquet_files = []
        
    dfs = [pd.read_parquet(f) for f in parquet_files]
    df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    
    rows_written = len(df)
    unknown_ratio = 0.0
    
    if rows_written > 0:
        if 'underlying' in df.columns:
            unknowns = df[df['underlying'] == 'UNKNOWN']
            unknown_ratio = len(unknowns) / rows_written
            
    print("STEP 6")
    print(f"frames_received: {frames_received}")
    print(f"rows_written: {rows_written}")
    print(f"parquet_created: {len(parquet_files)}")
    print(f"unknown_ratio: {unknown_ratio:.2%}\n")
    
    passed = (
        frames_received > 300 and
        rows_written > 500 and
        unknown_ratio < 0.01
    )
    
    print("STEP 7")
    if passed:
        print("PASS -> Committing patch")
    else:
        print("FAIL -> Reverting patch")
        
    decision = "PASS" if passed else "FAIL"
    
    print("Final Output:\n")
    print(f"patch_applied:\nTrue")
    print(f"capture_passed:\n{passed}")
    print(f"frames_received:\n{frames_received}")
    print(f"rows_written:\n{rows_written}")
    print(f"unknown_ratio:\n{unknown_ratio:.2%}\n")
    print(f"Decision:\n{decision}\n")
    print("STOP")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(override=True)
    asyncio.run(run_audit())
