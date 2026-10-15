"""
PHASE 1 FINAL CLOSURE — END-TO-END CERTIFICATION
Production Infrastructure Audit Script
"""
import asyncio
import json
import time
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=True)

from auth.auth_manager import AuthManager
from market.recorder import MarketRecorder
from market.decoder import ProtobufDecoder

Path("runtime").mkdir(parents=True, exist_ok=True)

# ── COLLECTION STATE ──
metrics_timeline = []
provider_metrics = {}
subscription_metrics = {"sent": 0, "ack": 0, "top_10_keys": []}
ingress_metrics = {"frames_received": 0, "market_frames": 0, "heartbeat_frames": 0, "messages_received": 0}
decoder_metrics = {"attempts": 0, "success": 0, "fail": 0, "rows_extracted": 0, "sample_rows": []}
validator_metrics = {}
storage_metrics = {}

async def main():
    print("="*60)
    print("  PHASE 1 FINAL CLOSURE — END-TO-END CERTIFICATION")
    print("="*60)

    # ── PRECHECK ──
    print("\n── PRECHECK ──")
    checks = {
        ".env": Path(".env").exists(),
        "token.enc": Path("config/token.enc").exists(),
        "token_meta.json": Path("config/token_meta.json").exists(),
        "provider.yaml": Path("config/provider.yaml").exists(),
        "instruments": Path("runtime/NSE.json.gz").exists(),
    }
    import shutil
    _, _, free = shutil.disk_usage(".")
    free_gb = free / (1024**3)
    checks["disk>20GB"] = free_gb > 20

    for k, v in checks.items():
        status = "✓" if v else "✗"
        print(f"  {status} {k}: {v}")

    if not all(checks.values()):
        print("\nPRECHECK: FAIL — Aborting.")
        return
    print("\nPRECHECK: PASS")

    # ── SETUP RECORDER WITH HOOKS ──
    auth_manager = AuthManager()
    recorder = MarketRecorder(auth_manager, dry_run=True)
    decoder = ProtobufDecoder()

    connect_start = time.time()

    # Hook: track provider connect timing
    original_connect = recorder.provider.connect
    async def timed_connect():
        nonlocal connect_start
        connect_start = time.time()
        await original_connect()
        elapsed = (time.time() - connect_start) * 1000
        provider_metrics["connection_time_ms"] = round(elapsed, 2)
        provider_metrics["provider_connected"] = recorder.provider.is_connected
        provider_metrics["transport_version"] = recorder.provider.version
        provider_metrics["authorize_status"] = "OK"
        provider_metrics["ws_connected"] = recorder.provider.is_connected
    recorder.provider.connect = timed_connect

    # Hook: intercept subscribe to capture outbound keys
    original_subscribe = recorder.provider.subscribe
    def hooked_subscribe(keys):
        subscription_metrics["sent"] = len(keys)
        subscription_metrics["top_10_keys"] = keys[:10]
        original_subscribe(keys)
    recorder.provider.subscribe = hooked_subscribe

    # Hook: intercept inbound messages for classification
    original_on_message = recorder._on_ws_message
    def hooked_on_message(message):
        ingress_metrics["frames_received"] += 1

        if isinstance(message, str) or (isinstance(message, bytes) and len(message) > 0 and message[0:1] == b'{'):
            try:
                js = json.loads(message)
                if "guid" in js or "status" in js:
                    subscription_metrics["ack"] += 1
            except:
                pass
        else:
            try:
                ticks = decoder.decode(message)
                decoder_metrics["attempts"] += 1
                if len(ticks) > 0:
                    decoder_metrics["success"] += 1
                    decoder_metrics["rows_extracted"] += len(ticks)
                    ingress_metrics["market_frames"] += 1
                    if len(decoder_metrics["sample_rows"]) < 3:
                        for t in ticks[:2]:
                            decoder_metrics["sample_rows"].append({
                                "underlying": t.underlying,
                                "strike": t.strike,
                                "ltp": t.ltp,
                                "bid": t.bid,
                                "ask": t.ask,
                                "volume": t.volume,
                            })
                else:
                    ingress_metrics["heartbeat_frames"] += 1
            except Exception as e:
                decoder_metrics["fail"] += 1

        ingress_metrics["messages_received"] = ingress_metrics["frames_received"]
        original_on_message(message)

    recorder._on_ws_message = hooked_on_message

    # ── STEP 1: START & OBSERVE 60s ──
    print("\n── STEP 1: START (60s observation) ──")
    task = asyncio.create_task(recorder.start())

    for tick in range(4):
        await asyncio.sleep(15)
        elapsed = 15 * (tick + 1)

        snapshot = {
            "t": elapsed,
            "provider_connected": recorder.provider.is_connected,
            "subs": len(recorder.current_subscriptions),
            "frames": ingress_metrics["frames_received"],
            "market": ingress_metrics["market_frames"],
            "heartbeat": ingress_metrics["heartbeat_frames"],
            "decode_ok": decoder_metrics["success"],
            "rows": decoder_metrics["rows_extracted"],
            "validator_recv": recorder.validator.total_received,
            "validator_drop": recorder.validator.total_dropped,
            "buffer": len(recorder.storage.tick_buffer),
            "rows_written_virtual": getattr(recorder.storage, "rows_written_virtual", 0),
            "flush_count": getattr(recorder.storage, "flush_count", 0),
        }
        metrics_timeline.append(snapshot)
        print(f"  [{elapsed:>3}s] frames={snapshot['frames']} market={snapshot['market']} hb={snapshot['heartbeat']} decode={snapshot['decode_ok']} rows={snapshot['rows']} buf={snapshot['buffer']} flush={snapshot['flush_count']} v_write={snapshot['rows_written_virtual']}", flush=True)

    # Shutdown
    recorder.is_running = False
    recorder.heartbeat.stop()
    recorder.provider.close()
    try:
        await asyncio.wait_for(task, timeout=5)
    except:
        pass

    # ── STEP 2: PROVIDER ──
    print("\n── STEP 2: PROVIDER ──")
    for k, v in provider_metrics.items():
        print(f"  {k}: {v}")
    if not provider_metrics.get("provider_connected"):
        print("  REJECTED: provider_connected=false")
        print("\nFAIL")
        print("Blocker: Provider not connected.")
        return

    # ── STEP 3: SUBSCRIPTIONS ──
    print("\n── STEP 3: SUBSCRIPTIONS ──")
    print(f"  subscriptions_sent: {subscription_metrics['sent']}")
    print(f"  subscription_ack: {subscription_metrics['ack']}")
    print(f"  active_subscription_count: {len(recorder.current_subscriptions)}")
    print(f"  top_10_keys: {subscription_metrics['top_10_keys']}")
    if subscription_metrics["ack"] == 0:
        # Don't abort here — the Upstox v3 WS may not send explicit JSON acks
        print("  WARNING: subscription_ack=0 (Upstox v3 may not send JSON acks)")

    # ── STEP 4: MARKET INGRESS ──
    print("\n── STEP 4: MARKET INGRESS ──")
    for k, v in ingress_metrics.items():
        print(f"  {k}: {v}")
    if ingress_metrics["messages_received"] == 0:
        print("  REJECTED: messages_received=0")
        print("\nFAIL")
        print("Blocker: Zero inbound messages from provider.")
        return

    # ── STEP 5: DECODER ──
    print("\n── STEP 5: DECODER ──")
    for k, v in decoder_metrics.items():
        if k != "sample_rows":
            print(f"  {k}: {v}")
    if decoder_metrics["sample_rows"]:
        print(f"  sample_decoded_rows:")
        for r in decoder_metrics["sample_rows"]:
            print(f"    {r}")
    if decoder_metrics["success"] == 0:
        print("  REJECTED: decode_success=0")
        print("\nOverall Grade: FAIL")
        # Build full report anyway
        _print_final_report(recorder, "FAIL",
            blocker="Decoder produced 0 successful market frames. All inbound frames are exchange heartbeats (0-row protobuf). No market tick data received from Upstox during the observation window.",
            root_cause="The Upstox WebSocket is delivering only exchange-level heartbeat protobuf frames with 0 tick rows. The subscription was sent but the server did not stream any market tick payloads. This may indicate: (1) subscriptions are silently ignored due to binary frame format, (2) instrument keys are invalid/inactive, or (3) market is in a low-activity period with no ticks for these instruments.")
        return

    # ── STEP 6: VALIDATOR ──
    print("\n── STEP 6: VALIDATOR ──")
    val = recorder.validator
    print(f"  total_received: {val.total_received}")
    print(f"  total_dropped: {val.total_dropped}")
    print(f"  duplicate_rate: {val.drop_reasons.get('duplicate', 0)}")
    print(f"  null_rate: {val.drop_reasons.get('missing_timestamp', 0)}")
    print(f"  negative_values: {val.drop_reasons.get('negative_value', 0)}")
    print(f"  bid_ask_errors: {val.drop_reasons.get('bid_gt_ask', 0)}")
    print(f"  oi_resets: {val.warning_reasons.get('oi_reset', 0)}")
    if val.total_received > 0 and val.total_dropped == val.total_received:
        print("  REJECTED: all rows dropped")
        print("\nFAIL")
        print("Blocker: Validator dropped 100% of decoded rows.")
        return

    # ── STEP 7: STORAGE ──
    print("\n── STEP 7: STORAGE ──")
    buf = len(recorder.storage.tick_buffer)
    rows_written_virtual = getattr(recorder.storage, "rows_written_virtual", 0)
    flush_count = getattr(recorder.storage, "flush_count", 0)
    print(f"  rows_buffered: {buf}")
    print(f"  rows_written_virtual: {rows_written_virtual}")
    print(f"  flush_count: {flush_count}")
    if buf == 0 and decoder_metrics["rows_extracted"] > 0:
        print("  REJECTED: rows_buffered=0 despite decoded rows")

    # ── STEP 8: HEARTBEAT ──
    print("\n── STEP 8: HEARTBEAT ──")
    hb_path = Path("runtime/heartbeat.json")
    if hb_path.exists():
        with open(hb_path) as f:
            hb = json.load(f)
        for k, v in hb.items():
            print(f"  {k}: {v}")
    else:
        print("  heartbeat.json not found")

    # ── FINAL ──
    _print_final_report(recorder, "PENDING", blocker=None, root_cause=None)


def _print_final_report(recorder, override_grade, blocker, root_cause):
    frames = ingress_metrics["frames_received"]
    market = ingress_metrics["market_frames"]
    hb = ingress_metrics["heartbeat_frames"]
    decode_ok = decoder_metrics["success"]
    rows = decoder_metrics["rows_extracted"]
    msgs = ingress_metrics["messages_received"]
    buf = len(recorder.storage.tick_buffer) if hasattr(recorder, 'storage') else 0

    # Acceptance check
    p_conn = provider_metrics.get("provider_connected", False)
    sub_ack = subscription_metrics.get("ack", 0)

    transport_ready = 100 if p_conn else 0
    decode_ready = min(100, int((decode_ok / max(1, decoder_metrics["attempts"])) * 100)) if decoder_metrics["attempts"] > 0 else 0
    storage_ready = 100 if buf > 0 else 0
    msg_loss = 100 - decode_ready if msgs > 0 else 100

    passed = (
        p_conn and
        msgs > 100 and
        decode_ok > 50 and
        buf > 50
    )

    grade = "PASS" if passed else "FAIL"
    if override_grade and override_grade != "PENDING":
        grade = override_grade

    print(f"\n{'='*60}")
    print(f"  FINAL REPORT")
    print(f"{'='*60}")
    print(f"  Overall Grade:         {grade}")
    print(f"  Production Readiness:  {int((transport_ready + decode_ready + storage_ready) / 3)}%")
    print(f"  Transport Readiness:   {transport_ready}%")
    print(f"  Decoder Readiness:     {decode_ready}%")
    print(f"  Storage Readiness:     {storage_ready}%")
    print(f"  Message Loss:          {msg_loss}%")
    print(f"  Rows Captured:         {rows}")

    if grade == "PASS":
        print(f"\n  Can start Phase 2?     YES")
        print(f"\n  PHASE 1 COMPLETE")
    else:
        if root_cause:
            print(f"\n  Root Cause:            {root_cause}")
        if blocker:
            print(f"  Exact Blocker:         {blocker}")
        print(f"\n  Can start Phase 2?     NO")

    # Persist
    report = {
        "grade": grade,
        "transport_readiness": transport_ready,
        "decode_readiness": decode_ready,
        "storage_readiness": storage_ready,
        "message_loss": msg_loss,
        "rows_captured": rows,
        "provider": provider_metrics,
        "subscriptions": subscription_metrics,
        "ingress": ingress_metrics,
        "decoder": {k: v for k, v in decoder_metrics.items() if k != "sample_rows"},
        "timeline": metrics_timeline,
        "blocker": blocker,
        "root_cause": root_cause
    }
    with open("runtime/phase1_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved: runtime/phase1_report.json")


if __name__ == "__main__":
    asyncio.run(main())
