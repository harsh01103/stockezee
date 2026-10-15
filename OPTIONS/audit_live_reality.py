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

async def run_live_capture(duration_sec=900):
    auth_manager = AuthManager()
    if not auth_manager.is_token_valid():
        logger.error("No valid Upstox token. Cannot run live observation.")
        return None, None
        
    # Start recorder in REAL mode (dry_run=False so it writes to disk)
    recorder = MarketRecorder(auth_manager, dry_run=False)
    
    # 1. Connect and verify
    await recorder.provider.connect()
    if not recorder.provider.is_connected:
        logger.error("Provider connect failed.")
        return None, None
        
    auth_meta = auth_manager.store.get_token_meta()
    if not auth_meta or auth_meta.state.value != "VALID":
        logger.error("Auth state is not VALID.")
        return None, None
        
    logger.info("Step 1: Provider connected, WS connected, Auth valid.")
    
    # Run the recorder main loop in the background
    task = asyncio.create_task(recorder.start())
    
    logger.info(f"Running live observation for {duration_sec} seconds...")
    start_time = time.time()
    
    # Step 2: Observe live every 30 sec
    while time.time() - start_time < duration_sec:
        await asyncio.sleep(30)
        logger.info(
            f"LIVE STATS: "
            f"Frames Rx: {recorder.validator.messages_received}, "
            f"Decode Success: {recorder.decoder.metrics.decode_success_rate:.1f}%, "
            f"Buffered: {len(recorder.storage.tick_buffer)}, "
            f"Written: {recorder.storage.rows_written_virtual}, "
            f"Active Subs: {len(recorder.current_subscriptions)}"
        )
    
    # Shut down cleanly
    logger.info("Stopping recorder...")
    recorder.is_running = False
    recorder.provider.close()
    recorder.heartbeat.stop()
    await recorder.storage.flush()
    await recorder.nse_client.close()
    
    try:
        await asyncio.wait_for(task, timeout=15.0)
    except asyncio.TimeoutError:
        pass
    except Exception as e:
        logger.error(f"Recorder exited with error: {e}")
        
    return recorder, start_time

def main():
    load_dotenv(override=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=int, default=15, help="Duration in minutes to run the live capture")
    args = parser.parse_args()
    
    duration_sec = args.minutes * 60
    
    recorder = None
    start_time = None
    auth_failed = False
    
    try:
        recorder, start_time = asyncio.run(run_live_capture(duration_sec))
    except Exception as e:
        logger.error(f"Failed to run capture: {e}")
        
    if not recorder:
        auth_failed = True
        
    # Get the latest data
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
    real_source_ratio = 0.0
    feature_motion = 0.0
    
    if not df.is_empty():
        # Step 3: Market Motion
        cols = ["spot", "ltp", "bid", "ask", "volume", "oi"]
        available_cols = [c for c in cols if c in df.columns]
        
        moving_cols = 0
        if available_cols:
            for c in available_cols:
                std = df[c].std()
                if std is not None and std > 0.0:
                    moving_cols += 1
            movement_score = moving_cols / len(available_cols)
            
        # Step 4: Pipeline Conversion
        # In reality, decoding & validation happened live. 
        # We can calculate ratios:
        decode_ratio = recorder.decoder.metrics.decode_success_rate / 100.0 if recorder.decoder.metrics.total_attempted > 0 else 0.0
        # Validator drop rate
        val_pass_ratio = (recorder.validator.messages_received - recorder.validator.messages_rejected) / recorder.validator.messages_received if recorder.validator.messages_received > 0 else 0.0
        pipeline_conversion = min(decode_ratio, val_pass_ratio)
        
        # Step 5: Raw Certification
        if all(c in df.columns for c in ["underlying", "expiry", "strike", "option_type"]):
            unique_instruments = df.select(["underlying", "expiry", "strike", "option_type"]).unique().height
            
        if "source_type" in df.columns:
            real_rows = df.filter(pl.col("source_type") == "REAL").height
            real_source_ratio = real_rows / rows_written if rows_written > 0 else 0.0
            
    else:
        pipeline_conversion = 0.0

    # Step 6: Feature Sanity
    # Run build_features --dry-run programmatically
    logger.info("Running Step 6: Feature Sanity via build_features(dry_run=True)")
    try:
        res = build_features(now_str, dry_run=True)
        df_features = res.get("df_features")
        if df_features is not None and not df_features.is_empty():
            # Calculate moving_feature_ratio
            num_cols = df_features.select(pl.selectors.numeric()).columns
            moving_feat = 0
            for c in num_cols:
                # Need to check variance, but we will accept std > 0 or max != min
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

    # Decision
    pass1 = rows_written > 1000
    pass2 = movement_score > 0.60
    pass3 = feature_motion > 0.50
    pass4 = real_source_ratio == 1.0
    pass5 = pipeline_conversion > 0.95
    pass6 = unique_instruments >= 10
    
    passed = not auth_failed and pass1 and pass2 and pass3 and pass4 and pass5 and pass6
    
    root_cause = "NONE"
    if not passed:
        if auth_failed:
            root_cause = "Failed to connect to provider. Auth token is invalid or expired."
        elif rows_written <= 1000:
            root_cause = "Insufficient rows written during live capture."
        elif unique_instruments < 10:
            root_cause = "Not enough unique instruments captured."
        elif real_source_ratio != 1.0:
            root_cause = "Synthetic/Mock data leaked into the live capture."
        elif pipeline_conversion <= 0.95:
            root_cause = "Pipeline conversion rate is below 95% (data dropped at decoder or validator)."
        elif movement_score <= 0.60:
            root_cause = "Raw market motion is too low (market flat or bad mappings)."
        elif feature_motion <= 0.50:
            root_cause = "Derived feature motion is too low (features are static despite raw ticks)."
            
    grade = "PASS" if passed else "FAIL"
    
    report = {
        "grade": grade,
        "rows_written": rows_written,
        "movement_score": movement_score,
        "feature_motion": feature_motion,
        "real_source_ratio": real_source_ratio,
        "pipeline_conversion": pipeline_conversion,
        "root_cause": root_cause
    }
    
    Path("reports").mkdir(exist_ok=True)
    with open("reports/live_reality_cert.json", "w") as f:
        json.dump(report, f, indent=2)
        
    print("\nFINAL OUTPUT")
    print(f"Grade: {report['grade']}")
    print(f"Rows Written: {report['rows_written']}")
    print(f"Movement Score: {report['movement_score']:.2f}")
    print(f"Feature Motion: {report['feature_motion']:.2f}")
    print(f"Real Source Ratio: {report['real_source_ratio']:.2f}")
    print(f"Pipeline Conversion: {report['pipeline_conversion']:.2f}")
    print(f"Root Cause: {report['root_cause']}")
    
    if passed:
        print("\nPASS")
    else:
        print("\nFAIL")

if __name__ == "__main__":
    main()
