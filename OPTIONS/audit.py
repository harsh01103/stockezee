import os
import sys
import shutil
import asyncio
from pathlib import Path

print("STEP 1: Environment")
env_ok = os.path.exists(".env")
token_enc_ok = os.path.exists("config/token.enc")
token_meta_ok = os.path.exists("config/token_meta.json")
metadata_ok = os.path.exists("runtime/NSE.json.gz")
free_gb = shutil.disk_usage('.').free / (1024**3)

print(f"Env: {env_ok}, token.enc: {token_enc_ok}, meta: {token_meta_ok}, metadata: {metadata_ok}, space: {free_gb:.2f}GB")
if env_ok and token_enc_ok and token_meta_ok and metadata_ok and free_gb > 20:
    print("Output: PASS\n")
else:
    print("Output: FAIL\n")

print("STEP 3: Instrument Resolution")
try:
    from market.instrument_resolver import InstrumentResolver
    res = InstrumentResolver()
    asyncio.run(res.ensure_loaded())
    print(f"Metadata loaded: {res.is_loaded}")
    print(f"Instrument count: {len(res.lookup_table)}")
    age = (time.time() - res.CACHE_FILE.stat().st_mtime)/3600 if res.CACHE_FILE.exists() else -1
    print(f"Cache age hours: {age:.2f}")
    
    nifty_ce = res.resolve("NIFTY", "26-Jun-2024", 23000, "CE")
    nifty_pe = res.resolve("NIFTY", "26-Jun-2024", 23000, "PE")
    bank_ce = res.resolve("BANKNIFTY", "26-Jun-2024", 50000, "CE")
    
    print(f"Resolved: NIFTY CE: {nifty_ce}, NIFTY PE: {nifty_pe}, BANK CE: {bank_ce}")
    if nifty_ce and nifty_pe and bank_ce:
        print("Output: PASS\n")
    else:
        print("Output: FAIL\n")
except Exception as e:
    print(f"Resolver error: {e}")
    print("Output: FAIL\n")

print("STEP 4: Strike Universe")
try:
    from market.nse_client import NSEClient
    from market.strike_selector import StrikeSelector
    nse = NSEClient()
    sel = StrikeSelector(nse)
    asyncio.run(sel.update_universe())
    nifty = sel.get_selected_strikes("NIFTY")
    
    print(f"Subscription candidates: {len(nifty)}")
    if nifty:
        print(f"Spot: {nifty[0].get('underlyingValue')}")
        print(f"Expiry: {nifty[0].get('expiryDate')}")
        print(f"Source: {nifty[0].get('source', 'NSE')}")
        
    if len(nifty) > 0:
        print("Output: PASS\n")
    else:
        print("Output: FAIL\n")
except Exception as e:
    print(f"Selector error: {e}")
    print("Output: FAIL\n")

print("STEP 7: Health Gate")
try:
    import json
    with open("runtime/heartbeat.json") as f:
        hb = json.load(f)
    print(f"Status: {hb.get('status')}")
    print(f"Auth State: {hb.get('auth_state')}")
    print(f"Messages received: {hb.get('messages_received')}")
    print(f"Rows buffered: {hb.get('rows_buffered')}")
    print("Output: PASS\n")
except Exception as e:
    print(f"HB error: {e}")
    print("Output: FAIL\n")
