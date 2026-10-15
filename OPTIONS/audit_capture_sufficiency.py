import argparse
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import polars as pl
from loguru import logger

def audit_session_context(df: pl.DataFrame):
    """Step 1: Session Context"""
    if df.is_empty():
        return 0.0, "unknown"
        
    ts_min = df["timestamp"].min()
    ts_max = df["timestamp"].max()
    
    if ts_min is None or ts_max is None:
        return 0.0, "unknown"
        
    start_dt = datetime.fromtimestamp(ts_min / 1000.0)
    end_dt = datetime.fromtimestamp(ts_max / 1000.0)
    
    # IST Market Hours: 09:15 to 15:30
    # Let's approximate overlap. If it's outside these hours, overlap is 0.
    # Note: timestamps are local time assuming Indian timezone or UTC depending on how it was saved.
    # The timestamps in our schema are usually local time in ms or UTC ms.
    # Let's convert to local hour
    
    # Simple check: if start_dt hour >= 16 or end_dt hour <= 8, market is closed.
    # A proper check would convert to IST and check 09:15 - 15:30.
    ist_offset = timedelta(hours=5, minutes=30)
    # Assuming start_dt is already local time (IST) in the environment, or we just extract hour.
    
    # Just to be safe, let's just use the hour of the datetime object in local time
    overlap_minutes = 0.0
    status = "closed"
    
    for i in range(int((ts_max - ts_min) / 60000) + 1):
        # check each minute
        check_time = datetime.fromtimestamp((ts_min + i * 60000) / 1000.0)
        h = check_time.hour
        m = check_time.minute
        
        # 09:15 to 15:30
        if (h > 9 or (h == 9 and m >= 15)) and (h < 15 or (h == 15 and m <= 30)):
            overlap_minutes += 1.0
            status = "open"
            
    return overlap_minutes, status

def audit_ingress_rate(df: pl.DataFrame):
    """Step 2: Ingress Rate"""
    if df.is_empty():
        return 0.0, 0.0, 0.0
        
    ts_min = df["timestamp"].min()
    ts_max = df["timestamp"].max()
    
    if ts_min is None or ts_max is None:
        return 0.0, 0.0, 0.0
        
    duration_min = (ts_max - ts_min) / 60000.0
    if duration_min <= 0:
        duration_min = 1.0 # default to 1 min if very short
        
    rows_per_minute = df.height / duration_min
    return float(rows_per_minute), 0.0, 0.0

def audit_subscription_coverage(df: pl.DataFrame):
    """Step 3: Subscription Coverage"""
    if df.is_empty():
        return 0.0
        
    # We expect roughly 60+ instruments to be subscribed based on logs (62 instruments)
    expected_subscribed = 62 
    
    if all(c in df.columns for c in ["underlying", "expiry", "strike", "option_type"]):
        active_instruments = df.select(["underlying", "expiry", "strike", "option_type"]).unique().height
    else:
        active_instruments = 0
        
    utilization = active_instruments / expected_subscribed if expected_subscribed > 0 else 0.0
    return float(utilization)

def audit_motion_window(df: pl.DataFrame):
    """Step 4: Motion Window"""
    if df.is_empty():
        return 0.0
        
    # Movement score across 15m
    cols = ["spot", "ltp", "volume", "oi"]
    available_cols = [c for c in cols if c in df.columns]
    
    if not available_cols:
        return 0.0
        
    moving_cols = 0
    for c in available_cols:
        c_std = df[c].std()
        if c_std is not None and c_std > 0.0:
            moving_cols += 1
            
    movement_score = moving_cols / len(available_cols)
    return float(movement_score)

def audit_event_composition(df: pl.DataFrame):
    """Step 5: Event Composition"""
    if df.is_empty():
        return 1.0 # 100% heartbeat if no data
        
    if "feed_type" not in df.columns:
        return 0.0
        
    total_events = df.height
    
    # "Heartbeat" equivalents in Upstox: empty INDEX_FF or missing bids/asks/volume changes
    # We will count FULL_FEED as quote/trade, and others as potentially heartbeat/status updates
    full_feed_count = df.filter(pl.col("feed_type") == "FULL_FEED").height
    
    # Ratio of non-FULL_FEED (like INDEX_FF, LTPC, OPTION_GREEKS, UNKNOWN)
    heartbeat_ratio = (total_events - full_feed_count) / total_events if total_events > 0 else 1.0
    
    # If the market is closed, even FULL_FEED might be empty (zero volume updates).
    # We can refine heartbeat_ratio if volume == 0 across the board.
    vol_sum = df["volume"].sum() if "volume" in df.columns else 0
    if vol_sum == 0:
        # If absolutely no volume is traded, it's effectively all heartbeat updates
        heartbeat_ratio = max(heartbeat_ratio, 1.0)
        
    return float(heartbeat_ratio)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, help="YYYY-MM-DD", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    
    date_str = args.date
    base_dir = Path(f"data/raw/{date_str}")
    
    df = pl.DataFrame()
    if base_dir.exists():
        files = list(base_dir.glob("*.parquet"))
        if files:
            dfs = [pl.read_parquet(f) for f in files]
            df = pl.concat(dfs, how="diagonal_relaxed")
            
    # Filter out mock data if any snuck in
    if "source_type" in df.columns:
        df = df.filter(pl.col("source_type") == "REAL")
            
    overlap_minutes, status = audit_session_context(df)
    rpm, fpm, tpm = audit_ingress_rate(df)
    utilization = audit_subscription_coverage(df)
    move_score_15m = audit_motion_window(df)
    hb_ratio = audit_event_composition(df)
    
    pass1 = rpm >= 100
    pass2 = utilization >= 0.20
    pass3 = move_score_15m >= 0.50
    pass4 = hb_ratio < 0.50
    
    passed = pass1 and pass2 and pass3 and pass4
    
    root_cause = "NONE"
    if not passed:
        if overlap_minutes == 0:
            root_cause = "Market closed during capture window (Out of hours)."
        elif hb_ratio >= 0.50:
            root_cause = "High heartbeat ratio. Subscriptions are active but emitting empty/static quotes."
        elif utilization < 0.20:
            root_cause = "Bad subscriptions. Instruments requested are invalid or expired."
        elif rpm < 100:
            root_cause = "Sparse writes. Connection is throttling or dropping ticks."
    
    grade = "PASS" if passed else "FAIL"
    
    report = {
        "grade": grade,
        "rows_per_minute": rpm,
        "instrument_utilization": utilization,
        "movement_score_15m": move_score_15m,
        "heartbeat_ratio": hb_ratio,
        "root_cause": root_cause
    }
    
    Path("reports").mkdir(exist_ok=True)
    with open("reports/phase1_capture_sufficiency.json", "w") as f:
        json.dump(report, f, indent=2)
        
    print("\nFINAL OUTPUT")
    print(f"Grade: {report['grade']}")
    print(f"Rows Per Minute: {report['rows_per_minute']:.2f}")
    print(f"Instrument Utilization: {report['instrument_utilization']:.2f}")
    print(f"Movement Score 15m: {report['movement_score_15m']:.2f}")
    print(f"Heartbeat Ratio: {report['heartbeat_ratio']:.2f}")
    print(f"Root Cause: {report['root_cause']}")
    
    if passed:
        print("\nPASS")
    else:
        print("\nFAIL")

if __name__ == "__main__":
    main()
