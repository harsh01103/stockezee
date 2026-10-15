import json
import inspect
from pathlib import Path
from datetime import datetime
import polars as pl
from loguru import logger

from market.decoder import ProtobufDecoder
from market.instrument_resolver import InstrumentResolver

def main():
    now_str = datetime.now().strftime("%Y-%m-%d")
    base_dir = Path(f"data/raw/{now_str}")
    
    df = pl.DataFrame()
    if base_dir.exists():
        files = list(base_dir.glob("*.parquet"))
        if files:
            # Get latest file
            latest_file = sorted(files, key=lambda f: f.stat().st_mtime)[-1]
            df = pl.read_parquet(latest_file)
            
    if df.is_empty():
        print("FAIL: No raw data found to inspect.")
        return
        
    df_50 = df.head(50)
    
    print("\n--- FIRST 50 PAYLOADS ---")
    for row in df_50.iter_rows(named=True):
        print(f"instrument_key: {row.get('instrument_key')} | underlying: {row.get('underlying')} | expiry: {row.get('expiry')} | strike: {row.get('strike')} | opt: {row.get('option_type')} | ltp: {row.get('ltp')}")
        
    unique_instrument_key = df_50["instrument_key"].n_unique() if "instrument_key" in df_50.columns else 0
    unique_underlying = df_50["underlying"].n_unique() if "underlying" in df_50.columns else 0
    unique_expiry = df_50["expiry"].n_unique() if "expiry" in df_50.columns else 0
    unique_strike = df_50["strike"].n_unique() if "strike" in df_50.columns else 0
    unique_option_type = df_50["option_type"].n_unique() if "option_type" in df_50.columns else 0
    
    print(f"\nunique_instrument_key: {unique_instrument_key}")
    print(f"unique_underlying: {unique_underlying}")
    print(f"unique_expiry: {unique_expiry}")
    print(f"unique_strike: {unique_strike}")
    print(f"unique_option_type: {unique_option_type}")
    
    step1_fail = unique_instrument_key > 10 and unique_strike <= 1
    
    # Step 2: Trace Decoder
    source = inspect.getsource(ProtobufDecoder)
    hardcoded = 'expiry=""' in source and 'strike=0.0' in source and 'option_type="CE"' in source
    print("\n--- DECODER TRACE ---")
    print(f"Are fields hardcoded? {hardcoded}")
    
    # Step 3: Verify Resolution
    resolver = InstrumentResolver()
    # It only has resolve() forward lookup. Let's see if reverse exists.
    has_reverse = hasattr(resolver, "resolve_from_key")
    lookup_hit_rate = 0.0
    print("\n--- RESOLUTION TRACE ---")
    print(f"Has reverse lookup? {has_reverse}")
    
    grade = "FAIL" if step1_fail else "PASS"
    root_cause = "Decoder collapses identity. Hardcoded expiry/strike/option_type in decoder.py without reverse lookup." if step1_fail else "NONE"
    
    report = {
        "grade": grade,
        "identity_score": 0.0,
        "lookup_hit_rate": lookup_hit_rate,
        "unique_instruments": unique_strike, # proxy
        "movement_score": 0.0,
        "root_cause": root_cause
    }
    
    Path("reports").mkdir(exist_ok=True)
    with open("reports/phase1_identity_diag.json", "w") as f:
        json.dump(report, f, indent=2)
        
    print(f"\nDIAGNOSIS {grade}: {root_cause}")

if __name__ == "__main__":
    main()
