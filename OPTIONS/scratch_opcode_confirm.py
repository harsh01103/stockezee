"""
SUBSCRIPTION OPCODE CONFIRMATION
Proves binary vs text frame hypothesis without modifying business logic.
"""
import asyncio
import json
import time
import websocket
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=True)

from auth.auth_manager import AuthManager
from market.recorder import MarketRecorder
from market.decoder import ProtobufDecoder

Path("runtime").mkdir(parents=True, exist_ok=True)

outbound_log = []
inbound_log = []

def get_opcode_name(data):
    if isinstance(data, bytes):
        return "BINARY (0x2)"
    elif isinstance(data, str):
        return "TEXT (0x1)"
    else:
        return f"UNKNOWN ({type(data).__name__})"

async def run_phase(label, patch_send=False):
    """Run a single phase — either with original binary send or patched text send."""
    print(f"\n{'='*60}", flush=True)
    print(f"  PHASE: {label}", flush=True)
    print(f"{'='*60}", flush=True)

    auth_manager = AuthManager()
    recorder = MarketRecorder(auth_manager, dry_run=True)

    phase_outbound = []
    phase_inbound = []
    decoder = ProtobufDecoder()

    # Step 1: Hook ws.send AFTER connect establishes the websocket
    original_connect = recorder.provider.connect

    async def hooked_connect():
        await original_connect()
        ws = recorder.provider.ws
        original_ws_send = ws.send

        def instrumented_send(data, *args, **kwargs):
            opcode = get_opcode_name(data)
            first_100 = ""
            if isinstance(data, bytes):
                first_100 = data[:100].hex()
            else:
                first_100 = data[:100]

            entry = {
                "timestamp": time.time(),
                "payload_type": type(data).__name__,
                "opcode": opcode,
                "payload_size": len(data),
                "first_100_bytes": first_100
            }
            phase_outbound.append(entry)
            outbound_log.append({"phase": label, **entry})
            print(f"  [SEND] opcode={opcode} size={len(data)}", flush=True)

            # If patching, convert bytes to str before sending
            if patch_send and isinstance(data, bytes):
                try:
                    data = data.decode('utf-8')
                    print(f"  [PATCH] Converted bytes -> str (TEXT frame)", flush=True)
                except UnicodeDecodeError:
                    pass  # Not JSON, send as-is

            original_ws_send(data, *args, **kwargs)

        ws.send = instrumented_send

    recorder.provider.connect = hooked_connect

    # Step 2: Hook inbound messages
    original_on_message = recorder._on_ws_message

    def hooked_on_message(message):
        msg_type = "binary" if isinstance(message, bytes) else "text"
        classification = "unknown"

        if msg_type == "text" or (msg_type == "binary" and len(message) > 0 and message[0:1] == b'{'):
            try:
                js = json.loads(message)
                if "guid" in js or "status" in js:
                    classification = "subscribe_ack"
                elif "error" in js:
                    classification = "error"
            except:
                pass
        else:
            try:
                ticks = decoder.decode(message)
                classification = "market_frame" if len(ticks) > 0 else "heartbeat"
            except:
                classification = "unknown"

        entry = {
            "timestamp": time.time(),
            "classification": classification,
            "type": msg_type,
            "size": len(message)
        }
        phase_inbound.append(entry)
        inbound_log.append({"phase": label, **entry})

        if classification != "heartbeat":
            print(f"  [RECV] class={classification} type={msg_type} size={len(message)}", flush=True)

        original_on_message(message)

    recorder._on_ws_message = hooked_on_message

    # Run
    task = asyncio.create_task(recorder.start())

    observe_sec = 60
    print(f"  Observing for {observe_sec} seconds...", flush=True)
    await asyncio.sleep(observe_sec)

    # Shutdown
    recorder.is_running = False
    recorder.heartbeat.stop()
    recorder.provider.close()
    try:
        await asyncio.wait_for(task, timeout=5)
    except:
        pass

    # Collect metrics
    acks = len([i for i in phase_inbound if i["classification"] == "subscribe_ack"])
    market = len([i for i in phase_inbound if i["classification"] == "market_frame"])
    heartbeats = len([i for i in phase_inbound if i["classification"] == "heartbeat"])
    messages_total = len(phase_inbound)
    sends = len(phase_outbound)
    opcodes = [o["opcode"] for o in phase_outbound]

    result = {
        "phase": label,
        "sends": sends,
        "opcodes": opcodes,
        "subscription_ack": acks,
        "market_updates": market,
        "heartbeats": heartbeats,
        "messages_received": messages_total,
        "rows": recorder.validator.total_received
    }

    print(f"\n  Results for {label}:", flush=True)
    print(f"    Sends: {sends}", flush=True)
    print(f"    Opcodes: {opcodes}", flush=True)
    print(f"    Subscription ACKs: {acks}", flush=True)
    print(f"    Market updates: {market}", flush=True)
    print(f"    Heartbeats: {heartbeats}", flush=True)
    print(f"    Messages received: {messages_total}", flush=True)
    print(f"    Rows (validator): {recorder.validator.total_received}", flush=True)

    return result


async def main():
    # BEFORE: Original binary send
    before = await run_phase("BEFORE (binary .encode)", patch_send=False)

    await asyncio.sleep(3)

    # AFTER: Patched text send
    after = await run_phase("AFTER (text str)", patch_send=True)

    # Persist
    with open("runtime/ws_outbound.json", "w") as f:
        json.dump(outbound_log, f, indent=2)

    # FINAL REPORT
    print(f"\n{'='*60}", flush=True)
    print(f"  FINAL REPORT", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"  Before opcode:   {before['opcodes']}", flush=True)
    print(f"  After opcode:    {after['opcodes']}", flush=True)
    print(f"  Ack delta:       {before['subscription_ack']} -> {after['subscription_ack']}", flush=True)
    print(f"  Message delta:   {before['messages_received']} -> {after['messages_received']}", flush=True)
    print(f"  Rows delta:      {before['rows']} -> {after['rows']}", flush=True)

    ack_improved = after["subscription_ack"] > before["subscription_ack"]
    msg_improved = after["market_updates"] > before["market_updates"]
    rows_improved = after["rows"] > before["rows"]

    if ack_improved or msg_improved or rows_improved:
        print(f"\n  Decision: CONFIRMED", flush=True)
        print(f"  Binary opcode was the root cause.", flush=True)
        print(f"  Text frame subscription activates market data.", flush=True)
    else:
        print(f"\n  Decision: REJECTED", flush=True)
        print(f"  Opcode change did not improve results.", flush=True)
        print(f"  Root cause is elsewhere.", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
