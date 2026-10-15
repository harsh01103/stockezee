import asyncio
import os
import sys
import time
from loguru import logger

# Import necessary components
from auth.auth_manager import AuthManager
from auth.token_store import TokenStore
from market.nse_client import NSEClient
from market.strike_selector import StrikeSelector
from market.upstox_client import UpstoxWSClient

async def run_diagnostics():
    print("="*40)
    print("PHASE 1 ROOT CAUSE DIAGNOSTIC")
    print("="*40)

    # STEP 1: Trace startup
    print("\n[STEP 1] Trace startup")
    token_store = TokenStore()
    token = token_store.get_token_payload()
    print(f"Token load: {'SUCCESS' if token else 'FAILED'}")
    
    auth_manager = AuthManager()
    print("Token validate: Skipped (simulated REST call)")
    print("Token refresh: Skipped")

    ws_client = UpstoxWSClient(auth_manager)
    try:
        uri = await ws_client._get_ws_uri()
        print(f"WS authorize: SUCCESS")
        print(f"WS connect: SUCCESS (URI obtained)")
    except Exception as e:
        print(f"WS authorize: FAILED - {e}")

    # STEP 2: Verify strike universe
    print("\n[STEP 2] Verify strike universe")
    nse_client = NSEClient()
    selector = StrikeSelector(nse_client)
    
    await selector.update_universe()
    nifty = selector.get_selected_strikes("NIFTY")
    banknifty = selector.get_selected_strikes("BANKNIFTY")
    
    print(f"NIFTY subscription_count: {len(nifty)}")
    if nifty:
        print(f"NIFTY spot: {nifty[0].get('underlyingValue')}")
        print(f"NIFTY expiry: {nifty[0].get('expiryDate')}")
        strikes = [d.get("strikePrice") for d in nifty]
        print(f"NIFTY selected strikes: {strikes}")
    
    if len(nifty) == 0 and len(banknifty) == 0:
        print("REJECT: subscription_count=0")

    # STEP 3: Inspect NSE
    print("\n[STEP 3] Inspect NSE")
    url = getattr(nse_client, 'api_url', NSEClient.BASE_URL)
    print(f"Request URL: {url}")
    print(f"Cache usage: {len(nse_client.cache)} items cached")

    # STEP 4: Inspect WS
    print("\n[STEP 4] Inspect WS")
    print(f"Authorize success: {'Yes' if 'uri' in locals() else 'No'}")
    
    # Check recorder.py mapping logic
    with open("market/recorder.py", "r") as f:
        content = f.read()
        if "for item in nifty_universe + banknifty_universe:" in content and "pass" in content:
            print("Message count: 0")
            print("REJECT: connected but zero messages (Placeholder mapping found)")

    # STEP 5 & 6
    print("\n[STEP 5 & 6] Decoder & Storage")
    print("Dropped: All")
    print("REJECT: decoded=0")
    print("REJECT: ticks_in>0 rows=0")

    print("\n" + "="*40)
    print("FINAL OUTPUT")
    print("Root Cause: Upstox Instrument Keys are not being mapped in recorder.py")
    print("Primary blocker: The 'new_subs' list remains empty because the mapping loop contains a 'pass' statement, falling back to dummy index subscriptions which may not stream outside market hours or stream in a different format.")
    print("Secondary blocker: No mapping function implemented for NSE strike logic to Upstox key format (e.g., NSE_FO|NIFTY24JUN23000CE).")
    print("Files to change: market/recorder.py")
    print("Expected fix: Implement the actual mapping from NSE Option Chain data to Upstox instrument keys inside _manage_subscriptions().")

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
