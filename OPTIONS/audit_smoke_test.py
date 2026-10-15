import asyncio
import sys
import time
import json
from loguru import logger
from dotenv import load_dotenv

from auth.auth_manager import AuthManager
from market.recorder import MarketRecorder

async def run_smoke_test():
    auth_manager = AuthManager()
    if not auth_manager.is_token_valid():
        print(json.dumps({"error": "Auth failed"}))
        return

    recorder = MarketRecorder(auth_manager, dry_run=True)
    
    # Connect
    await recorder.provider.connect()
    provider_connected = recorder.provider.is_connected
    ws_connected = recorder.provider.is_connected
    
    if not provider_connected:
        print(json.dumps({"error": "Provider not connected"}))
        return
        
    task = asyncio.create_task(recorder.start())
    
    # Observe for 60 seconds
    await asyncio.sleep(60)
    
    # Collect stats
    messages_received = recorder.validator.messages_received
    active_subscriptions = len(recorder.current_subscriptions)
    subscription_ack = active_subscriptions > 0 and messages_received > 0
    
    # Shutdown
    recorder.is_running = False
    recorder.provider.close()
    recorder.heartbeat.stop()
    await recorder.nse_client.close()
    
    try:
        await asyncio.wait_for(task, timeout=5.0)
    except Exception:
        pass
        
    output = {
        "provider_connected": provider_connected,
        "ws_connected": ws_connected,
        "messages_received": messages_received,
        "subscription_ack": subscription_ack,
        "active_subscriptions": active_subscriptions
    }
    print("SMOKE_TEST_OUTPUT:" + json.dumps(output))

if __name__ == "__main__":
    load_dotenv(override=True)
    logger.remove() # disable logging to stdout so we can cleanly parse JSON
    asyncio.run(run_smoke_test())
