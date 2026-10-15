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

async def run_live_capture(duration_sec=300):
    auth_manager = AuthManager()
    if not auth_manager.is_token_valid():
        logger.error("No valid token. Cannot run live observation.")
        return None, None
        
    recorder = MarketRecorder(auth_manager, dry_run=False)
    await recorder.instrument_resolver.ensure_loaded()
    
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
    duration_sec = 60 # 1 minute for fast recertification
    
    try:
        recorder, start_time = asyncio.run(run_live_capture(duration_sec))
    except Exception as e:
        logger.error(f"Failed: {e}")
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
    lookup_hit_rate = 100.0
    
    field_loss_matrix = {}
    
    if not df.is_empty():
        cols = ["spot", "ltp", "bid", "ask", "volume", "oi"]
        available_cols = [c for c in cols if c in df.columns]
        
        # We only check movement on non-zero strikes
        if all(c in df.columns for c in ["underlying", "expiry", "strike", "option_type"]):
            df_options = df.filter(pl.col("strike") > 0)
            
            # Hit rate calculation based on UNKNOWN
            total_rows = df.height
            unresolved = df.filter(pl.col("underlying") == "UNKNOWN").height
            if total_rows > 0:
                lookup_hit_rate = ((total_rows - unresolved) / total_rows) * 100
            
            if not df_options.is_empty():
                unique_instruments = df_options.select(["underlying", "expiry", "strike", "option_type"]).unique().height
                
                moving_cols = 0
                for c in available_cols:
                    std = df_options[c].std()
                    if std is not None and std > 0.0:
                        moving_cols += 1
                        field_loss_matrix[c] = "PRESERVED"
                    else:
                        field_loss_matrix[c] = "LOST"
                        
                movement_score = moving_cols / len(available_cols)
                
                # feature motion
                num_cols = ["ltp", "bid", "ask", "volume", "oi"]
                moving_feat = 0
                for c in num_cols:
                    if c in df_options.columns:
                        c_min = df_options[c].min()
                        c_max = df_options[c].max()
                        if c_min is not None and c_max is not None and c_max > c_min:
                            moving_feat += 1
                feature_motion = moving_feat / len(num_cols)

    passed = (lookup_hit_rate > 95.0) and (movement_score > 0.30) and (feature_motion > 0.20)
    
    report = {
        "grade": "PASS" if passed else "FAIL",
        "root_layer": "decoder_partial_merge",
        "field_loss_matrix": field_loss_matrix,
        "lookup_hit_rate": lookup_hit_rate,
        "movement_score": movement_score,
        "feature_motion": feature_motion,
        "unique_instruments": unique_instruments,
        "rows_written": rows_written
    }
    
    Path("reports").mkdir(exist_ok=True)
    with open("reports/phase1_motion_forensics.json", "w") as f:
        json.dump(report, f, indent=2)
        
    print("\nFINAL OUTPUT")
    print(f"Grade: {report['grade']}")
    print(f"Lookup Hit Rate: {report['lookup_hit_rate']:.2f}%")
    print(f"Movement Score: {report['movement_score']:.2f}")
    print(f"Feature Motion: {report['feature_motion']:.2f}")
    print(f"Rows Written: {report['rows_written']}")
    
    if passed:
        print("\nPASS")
    else:
        print("\nFAIL")

if __name__ == "__main__":
    main()
