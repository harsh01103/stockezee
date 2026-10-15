import argparse
import asyncio
import json
import time
import sys
from pathlib import Path
from datetime import datetime
import polars as pl
from loguru import logger
from dotenv import load_dotenv

from auth.auth_manager import AuthManager
from market.recorder import MarketRecorder
from features.builder import build_features

async def run_live_capture(duration_sec=300):
    auth_manager = AuthManager()
    if not auth_manager.is_token_valid():
        logger.error("No valid Upstox token. Cannot run live observation.")
        return None, None
        
    recorder = MarketRecorder(auth_manager, dry_run=False)
    
    # Ensure resolver is loaded synchronously or awaited before start
    await recorder.instrument_resolver.ensure_loaded()
    
    # Connect
    await recorder.provider.connect()
    if not recorder.provider.is_connected:
        logger.error("Provider connect failed.")
        return None, None
        
    task = asyncio.create_task(recorder.start())
    
    logger.info(f"Running live observation for {duration_sec} seconds...")
    start_time = time.time()
    
    while time.time() - start_time < duration_sec:
        await asyncio.sleep(15)
        logger.info(f"LIVE STATS: Messages: {recorder.validator.messages_received}, Buffered: {len(recorder.storage.tick_buffer)}")
    
    logger.info("Stopping recorder...")
    recorder.is_running = False
    recorder.provider.close()
    recorder.heartbeat.stop()
    await recorder.storage.flush()
    await recorder.nse_client.close()
    
    try:
        await asyncio.wait_for(task, timeout=15.0)
    except Exception:
        pass
        
    return recorder, start_time

def main():
    load_dotenv(override=True)
    duration_sec = 300 # 5 minutes
    
    recorder = None
    try:
        recorder, start_time = asyncio.run(run_live_capture(duration_sec))
    except Exception as e:
        logger.error(f"Failed: {e}")
        
    if not recorder:
        print("FAIL: Failed to initialize or run recorder.")
        sys.exit(1)
        
    now_str = datetime.now().strftime("%Y-%m-%d")
    base_dir = Path(f"data/raw/{now_str}")
    
    df = pl.DataFrame()
    if base_dir.exists():
        files = list(base_dir.glob("*.parquet"))
        if files:
            recent_files = [f for f in files if (time.time() - f.stat().st_mtime) < (duration_sec + 60)]
            if recent_files:
                dfs = [pl.read_parquet(f) for f in recent_files]
                df = pl.concat(dfs, how="diagonal_relaxed")
                
    rows_written = df.height if not df.is_empty() else 0
    unique_instruments = 0
    movement_score = 0.0
    feature_motion = 0.0
    lookup_hit_rate = 100.0 # Approximate for now
    
    if not df.is_empty():
        cols = ["spot", "ltp", "bid", "ask", "volume", "oi"]
        available_cols = [c for c in cols if c in df.columns]
        
        moving_cols = 0
        if available_cols:
            for c in available_cols:
                std = df[c].std()
                if std is not None and std > 0.0:
                    moving_cols += 1
            movement_score = moving_cols / len(available_cols)
            
        if all(c in df.columns for c in ["underlying", "expiry", "strike", "option_type"]):
            # Count unique combinations where strike > 0
            df_options = df.filter(pl.col("strike") > 0)
            if not df_options.is_empty():
                unique_instruments = df_options.select(["underlying", "expiry", "strike", "option_type"]).unique().height
                
                # Check hit rate: ratio of non-zero strikes
                lookup_hit_rate = (df_options.height / df.height) * 100

    logger.info("Running Step 6: Feature Sanity")
    try:
        res = build_features(now_str, dry_run=True)
        df_features = res.get("df_features")
        if df_features is not None and not df_features.is_empty():
            num_cols = df_features.select(pl.selectors.numeric()).columns
            moving_feat = 0
            for c in num_cols:
                try:
                    c_min = df_features[c].min()
                    c_max = df_features[c].max()
                    if c_min is not None and c_max is not None and c_max > c_min:
                        moving_feat += 1
                except Exception:
                    pass
            feature_motion = moving_feat / len(num_cols) if num_cols else 0.0
    except Exception as e:
        logger.error(f"Feature sanity failed: {e}")
        feature_motion = 0.0

    pass1 = rows_written > 10000
    pass2 = unique_instruments > 30
    pass3 = movement_score > 0.40
    pass4 = feature_motion > 0.25
    
    passed = pass1 and pass2 and pass3 and pass4
    
    root_cause = "NONE"
    if not passed:
        if rows_written <= 10000:
            root_cause = "Not enough rows written in 5 mins."
        elif unique_instruments <= 30:
            root_cause = f"Not enough unique instruments ({unique_instruments} <= 30)."
        elif movement_score <= 0.40:
            root_cause = f"Movement score too low ({movement_score:.2f} <= 0.40)."
        elif feature_motion <= 0.25:
            root_cause = f"Feature motion too low ({feature_motion:.2f} <= 0.25)."
            
    grade = "PASS" if passed else "FAIL"
    
    report = {
        "grade": grade,
        "identity_score": 1.0 if unique_instruments > 30 else 0.0,
        "lookup_hit_rate": lookup_hit_rate,
        "unique_instruments": unique_instruments,
        "movement_score": movement_score,
        "root_cause": root_cause
    }
    
    Path("reports").mkdir(exist_ok=True)
    with open("reports/phase1_identity_certify.json", "w") as f:
        json.dump(report, f, indent=2)
        
    print("\nFINAL OUTPUT")
    print(f"Grade: {report['grade']}")
    print(f"Identity Score: {report['identity_score']:.2f}")
    print(f"Lookup Hit Rate: {report['lookup_hit_rate']:.2f}")
    print(f"Unique Instruments: {report['unique_instruments']}")
    print(f"Movement Score: {report['movement_score']:.2f}")
    print(f"Feature Motion: {feature_motion:.2f}")
    print(f"Root Cause: {report['root_cause']}")
    
    if passed:
        print("\nPASS")
    else:
        print("\nFAIL")

if __name__ == "__main__":
    main()
