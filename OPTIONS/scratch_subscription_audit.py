import asyncio
import os
import json
import time
from pathlib import Path
from auth.auth_manager import AuthManager
from market.recorder import MarketRecorder
from dotenv import load_dotenv
load_dotenv(override=True)

async def main():
    print("Starting Subscription Truth Audit...", flush=True)
    auth_manager = AuthManager()
    recorder = MarketRecorder(auth_manager, dry_run=True)
    
    # Hooks
    outbound_log = []
    inbound_log = []
    
    Path("runtime").mkdir(parents=True, exist_ok=True)
    
    # 1. Hook Provider send to capture outbound
    original_send = None
    
    def hooked_send(data, *args, **kwargs):
        # Record outbound
        try:
            if isinstance(data, bytes):
                js = json.loads(data.decode('utf-8'))
            else:
                js = json.loads(data)
                
            entry = {
                "timestamp": time.time(),
                "instrument_key": js.get("data", {}).get("instrumentKeys", []),
                "feed_mode": js.get("data", {}).get("mode", ""),
                "payload": data.decode('utf-8') if isinstance(data, bytes) else data,
                "count": len(js.get("data", {}).get("instrumentKeys", []))
            }
            outbound_log.append(entry)
            print(f"Captured Outbound Sub: {entry['count']} instruments", flush=True)
            with open("runtime/subscriptions.json", "w") as f:
                json.dump(outbound_log, f, indent=2)
                
        except Exception as e:
            print(f"Error logging outbound: {e}")
            
        original_send(data, *args, **kwargs)

    # We need to wait until the ws is created
    original_connect = recorder.provider.connect
    async def hooked_connect():
        await original_connect()
        nonlocal original_send
        original_send = recorder.provider.ws.send
        recorder.provider.ws.send = hooked_send
        
    recorder.provider.connect = hooked_connect

    # 2. Hook receive to capture inbound
    original_on_message = recorder._on_ws_message
    def hooked_on_message(message):
        try:
            msg_type = "binary" if isinstance(message, bytes) else "text"
            classification = "unknown"
            
            if msg_type == "text" or (msg_type == "binary" and message.startswith(b'{')):
                js = json.loads(message)
                if js.get("status") == "success" and "guid" in js:
                    if js["guid"].startswith("sub_"):
                        classification = "subscribe_ack"
                    elif js["guid"].startswith("unsub_"):
                        classification = "unsubscribe_ack"
                elif "error" in js:
                    classification = "error"
            else:
                # Market data or heartbeat
                # Assume heartbeat if size < 200 and no ticks
                from market.decoder import ProtobufDecoder
                decoder = ProtobufDecoder()
                ticks = decoder.decode(message)
                if len(ticks) > 0:
                    classification = "market_frame"
                else:
                    classification = "heartbeat"
                    
            entry = {
                "timestamp": time.time(),
                "classification": classification,
                "type": msg_type,
                "size": len(message)
            }
            inbound_log.append(entry)
            with open("runtime/provider_frames.json", "w") as f:
                json.dump(inbound_log, f, indent=2)
                
        except Exception as e:
            pass
            
        original_on_message(message)
        
    recorder._on_ws_message = hooked_on_message
    
    # Part 1: Normal observe
    print("\n--- PHASE 1: Normal Observe ---", flush=True)
    task = asyncio.create_task(recorder.start())
    
    await asyncio.sleep(60) # Wait 60s for normal run
    
    # Part 2: Control Test
    print("\n--- PHASE 2: Control Test ---", flush=True)
    # Clear logs
    outbound_log.clear()
    inbound_log.clear()
    
    # We will subscribe ONLY to 1 index, 1 call, 1 put using raw strings
    # We send it exactly as text instead of bytes
    
    control_subs = [
        "NSE_INDEX|Nifty 50",
        "NSE_FO|12345", # Some dummy call
        "NSE_FO|67890"  # Some dummy put
    ]
    
    control_payload = {
        "guid": "sub_control",
        "method": "sub",
        "data": {
            "mode": "full",
            "instrumentKeys": control_subs
        }
    }
    
    print("Sending control payload as TEXT (string)...", flush=True)
    recorder.provider.ws.send(json.dumps(control_payload))
    
    # Log it
    outbound_log.append({
        "timestamp": time.time(),
        "instrument_key": control_subs,
        "feed_mode": "full",
        "payload": json.dumps(control_payload),
        "count": 3
    })
    
    await asyncio.sleep(60) # Wait 60s for control run
    
    recorder.is_running = False
    recorder.heartbeat.stop()
    recorder.provider.close()
    
    try:
        await asyncio.wait_for(task, timeout=5)
    except:
        pass
        
    print("\n--- FINAL REPORT ---")
    
    # Analyze
    subs_sent = sum([o["count"] for o in outbound_log])
    subs_ack = len([i for i in inbound_log if i["classification"] == "subscribe_ack"])
    market_updates = len([i for i in inbound_log if i["classification"] == "market_frame"])
    heartbeats = len([i for i in inbound_log if i["classification"] == "heartbeat"])
    
    print(f"Subscription sent: {subs_sent}")
    print(f"Subscription ack: {subs_ack}")
    print(f"Market updates: {market_updates}")
    print(f"Activation ratio: {0 if subs_sent == 0 else (subs_ack / len(outbound_log)):.2f}")
    
    if subs_ack == 0 and heartbeats > 0:
        print("Root cause: Subscriptions are silently ignored by the provider because they are sent as binary frames instead of text frames.")
        print("Patch file: market/feed_provider.py")
        print("Recommendation: subscription format")
    elif subs_ack > 0 and market_updates == 0:
        print("Root cause: Provider acknowledged the subscription, but sent 0 market updates.")
        print("Patch file: market/feed_provider.py")
        print("Recommendation: feed mode or resolver")
    else:
        print("Root cause: Unknown")
        print("Patch file: Unknown")
        print("Recommendation: Unknown")

if __name__ == "__main__":
    asyncio.run(main())
