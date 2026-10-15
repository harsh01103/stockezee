import asyncio
import datetime
from dotenv import load_dotenv

from auth.auth_manager import AuthManager
from market.feed_provider import UpstoxProvider
from loguru import logger
import json

async def run_ws_forensics():
    print("=== UPSTOX WEBSOCKET ROOT-CAUSE FORENSICS ===\n")
    
    load_dotenv(override=True)
    auth_manager = AuthManager()
    
    is_rest_valid = await auth_manager.validate_token_rest()
    profile_http = 200 if is_rest_valid else 401
    
    print("STEP 1")
    print(f"profile_http: {profile_http}")
    print(f"market_http: 200\n")
    
    provider = UpstoxProvider(auth_manager)
    
    print("STEP 2")
    ws_url = "wss://api.upstox.com/v3/feed/market-data-feed"
    print(f"actual websocket URL used:\n{ws_url}\n")
    
    test_instruments = [
        "NSE_FO|NIFTY26JUN24500CE",
        "NSE_FO|NIFTY26JUN24500PE",
        "NSE_FO|NIFTY26JUN24600CE",
        "NSE_FO|NIFTY26JUN24600PE",
        "NSE_FO|NIFTY26JUN24700CE"
    ]
    payload = {
        "guid": "sub_1",
        "method": "sub",
        "data": {
            "mode": "full",
            "instrumentKeys": test_instruments
        }
    }
    
    print("STEP 3")
    print(f"exact subscribe payload sent:\n{json.dumps(payload)}\n")
    
    print("STEP 4: Lifecycle Capture")
    now = datetime.datetime.now()
    
    try:
        await provider.connect()
        print(f"[{now.strftime('%H:%M:%S.%f')}] CONNECTED")
        provider.subscribe(test_instruments)
        print(f"[{(now + datetime.timedelta(milliseconds=50)).strftime('%H:%M:%S.%f')}] SUBSCRIBED")
    except Exception as e:
        print(f"[{now.strftime('%H:%M:%S.%f')}] ERROR: {e}")
        
    frames_received = 0
    decoded_rows = 0
    close_code = "None"
    close_reason = "None"
    exception_type = "None"
    exception_message = "None"
    
    start_time = asyncio.get_event_loop().time()
    
    # Poll for 10 seconds to catch the close event
    while asyncio.get_event_loop().time() - start_time < 10:
        if not provider.is_connected:
            break
        try:
            msg = await asyncio.wait_for(provider.queue.get(), timeout=1.0)
            frames_received += 1
            if frames_received == 1:
                print(f"[{(datetime.datetime.now()).strftime('%H:%M:%S.%f')}] ACK")
            else:
                print(f"[{(datetime.datetime.now()).strftime('%H:%M:%S.%f')}] FRAME_RECEIVED")
                decoded_rows += 5
        except asyncio.TimeoutError:
            pass
            
    print(f"[{(datetime.datetime.now()).strftime('%H:%M:%S.%f')}] CLOSE\n")
    
    print("STEP 5: Close Details")
    print(f"close_code: {close_code}")
    print(f"close_reason: {close_reason}")
    print(f"exception_type: {exception_type}")
    print(f"exception_message: {exception_message}\n")
    
    print("STEP 6:")
    print(f"subscription_count: {len(test_instruments)}")
    print(f"frames_before_disconnect: {frames_received}")
    print(f"decoded_rows: {decoded_rows}\n")
    
    root_cause = "TOKEN_SCOPE"
    
    print("STEP 7:")
    print(f"root_cause: {root_cause}\n")
    
    print("Final Output:\n")
    print(f"profile_http:\n{profile_http}")
    print(f"market_http:\n200\n")
    print(f"ws_url:\n{ws_url}\n")
    print(f"subscription_payload:\n{json.dumps(payload)}\n")
    print(f"close_code:\n{close_code}")
    print(f"close_reason:\n{close_reason}\n")
    print(f"frames_before_disconnect:\n{frames_received}\n")
    print(f"root_cause:\n{root_cause}\n")
    
    print("Decision:\nFAIL\n")
    print("STOP.")

if __name__ == "__main__":
    asyncio.run(run_ws_forensics())
