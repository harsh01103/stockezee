"""
PHASE 1.5 - SUBSCRIPTION PROTOCOL FORENSICS
Determines why Upstox v3 ignores subscriptions.
"""
import asyncio
import json
import time
import websocket
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=True)

from auth.auth_manager import AuthManager
from market.feed_provider import UpstoxProvider
from market.decoder import ProtobufDecoder

outbound_log = []
inbound_log = []

async def run_experiment(name, payload_factory, wait_sec=15):
    print(f"\n{'='*60}")
    print(f"  EXPERIMENT: {name}")
    print(f"{'='*60}")
    
    auth_manager = AuthManager()
    provider = UpstoxProvider(auth_manager)
    decoder = ProtobufDecoder()
    
    # ── STEP 3: Verify provider contract ──
    if name == "A: minimal (Nifty 50)":
        token = auth_manager.get_access_token()
        url = provider.upstox_config.get(f"authorize_url_{provider.version}")
        print("\n  [CONTRACT] Authorize URL:", url)
        # We will print WS URL and Schema below
        
    try:
        ws_uri = await provider.authorize()
    except Exception as e:
        print(f"  Authorize failed: {e}")
        return None
        
    if name == "A: minimal (Nifty 50)":
        print("  [CONTRACT] WS URI:", ws_uri.split("?")[0] + "?...")
    
    provider.ws = websocket.WebSocketApp(
        ws_uri,
        on_open=provider._on_open,
        on_message=provider._on_message,
        on_error=provider._on_error,
        on_close=provider._on_close
    )
    
    # Hook send to capture Step 1
    original_send = provider.ws.send
    def hooked_send(data, *args, **kwargs):
        opcode = "BINARY (0x2)" if isinstance(data, bytes) else "TEXT (0x1)"
        try:
            js_payload = json.loads(data.decode('utf-8') if isinstance(data, bytes) else data)
        except:
            js_payload = "<not_json>"
            
        print(f"  [SEND] time={time.time():.3f} opcode={opcode} len={len(data)}")
        if js_payload != "<not_json>":
            keys = js_payload.get("data", {}).get("instrumentKeys", [])
            print(f"         count={len(keys)} schema={json.dumps(js_payload)}")
        else:
            print(f"         raw={data[:100]}")
            
        outbound_log.append({
            "exp": name,
            "timestamp": time.time(),
            "opcode": opcode,
            "length": len(data),
            "payload": js_payload
        })
        original_send(data, *args, **kwargs)
        
    provider.ws.send = hooked_send
    
    # Hook receive to capture Step 2
    original_on_message = provider._on_message
    exp_inbound = []
    
    def hooked_on_msg(ws, message):
        opcode = "BINARY" if isinstance(message, bytes) else "TEXT"
        first_200 = message[:200].hex() if isinstance(message, bytes) else message[:200]
        
        classification = "unknown"
        if opcode == "TEXT" or (opcode == "BINARY" and len(message) > 0 and message[0:1] == b'{'):
            try:
                js = json.loads(message)
                if "guid" in js or "status" in js: classification = "ack"
                elif "error" in js: classification = "error"
            except:
                pass
        else:
            try:
                ticks = decoder.decode(message)
                classification = "market_data" if len(ticks) > 0 else "heartbeat"
            except:
                classification = "unknown"
                
        # print(f"  [RECV] opcode={opcode} len={len(message)} class={classification}")
        exp_inbound.append(classification)
        inbound_log.append({
            "exp": name,
            "opcode": opcode,
            "length": len(message),
            "class": classification,
            "first_200": first_200
        })
        original_on_message(ws, message)
        
    provider._on_message = hooked_on_msg
    
    # Connect
    import threading
    provider.ws_thread = threading.Thread(target=provider.ws.run_forever, daemon=True)
    provider.ws_thread.start()
    
    provider.main_loop = asyncio.get_running_loop()
    for _ in range(50):
        if provider.is_connected: break
        await asyncio.sleep(0.1)
        
    if not provider.is_connected:
        print("  Connection failed.")
        return None
        
    # Send payload if factory provided
    payload = payload_factory() if payload_factory else None
    if payload:
        # provider.ws.send(json.dumps(payload).encode('utf-8'))
        # Using pure string for text frame as Upstox API might prefer it (though binary failed too)
        provider.ws.send(json.dumps(payload).encode('utf-8'))
        
    print(f"  Waiting {wait_sec}s...")
    await asyncio.sleep(wait_sec)
    
    provider.close()
    
    acks = exp_inbound.count("ack")
    market = exp_inbound.count("market_data")
    hb = exp_inbound.count("heartbeat")
    total = len(exp_inbound)
    
    return {
        "payload": payload,
        "acks": acks,
        "market": market,
        "hb": hb,
        "total": total
    }

async def main():
    results = {}
    
    # A: minimal Nifty 50
    results["A"] = await run_experiment("A: minimal (Nifty 50)", lambda: {
        "guid": "sub_A",
        "method": "sub",
        "data": {
            "mode": "full",
            "instrumentKeys": ["NSE_INDEX|Nifty 50"]
        }
    })
    
    # B: single option
    results["B"] = await run_experiment("B: single option", lambda: {
        "guid": "sub_B",
        "method": "sub",
        "data": {
            "mode": "full",
            "instrumentKeys": ["NSE_FO|75288"]
        }
    })
    
    # C: minimal payload (no mode)
    results["C"] = await run_experiment("C: minimal payload", lambda: {
        "guid": "sub_C",
        "method": "sub",
        "data": {
            "instrumentKeys": ["NSE_INDEX|Nifty 50"]
        }
    })
    
    # D1: mode ltpc
    results["D1"] = await run_experiment("D1: mode ltpc", lambda: {
        "guid": "sub_D1",
        "method": "sub",
        "data": {
            "mode": "ltpc",
            "instrumentKeys": ["NSE_INDEX|Nifty 50"]
        }
    })
    
    # D2: mode option_chain
    results["D2"] = await run_experiment("D2: mode option_chain", lambda: {
        "guid": "sub_D2",
        "method": "sub",
        "data": {
            "mode": "option_chain",
            "instrumentKeys": ["NSE_INDEX|Nifty 50"]
        }
    })
    
    # E: wait 30s without subscribing
    results["E"] = await run_experiment("E: wait without sub", lambda: None, wait_sec=30)
    
    # STEP 5 - Output matrix
    print(f"\n{'='*60}")
    print(f"  STEP 5: SERVER RESPONSE MATRIX")
    print(f"{'='*60}")
    print(f"{'EXP':<4} | {'ACK':<4} | {'MKT':<4} | {'HB':<4} | {'TOT':<4} | PAYLOAD")
    print("-" * 60)
    for exp, res in results.items():
        if res:
            p_str = json.dumps(res['payload']) if res['payload'] else "None"
            if len(p_str) > 30: p_str = p_str[:27] + "..."
            print(f"{exp:<4} | {res['acks']:<4} | {res['market']:<4} | {res['hb']:<4} | {res['total']:<4} | {p_str}")
        else:
            print(f"{exp:<4} | FAILED")

    print("\nCheck runtime/forensics.json for detailed logs.")
    with open("runtime/forensics.json", "w") as f:
        json.dump({"outbound": outbound_log, "inbound": inbound_log}, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
