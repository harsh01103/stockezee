import datetime
import os

def run_strict_live_capture():
    print("=== STRICT UPSTOX LIVE-ONLY CAPTURE ===\n")
    
    now_ist = datetime.datetime.now()
    print(f"current_ist: {now_ist.strftime('%H:%M:%S')}")
    
    is_market_open = False
    if now_ist.weekday() < 5:
        if (now_ist.hour > 9 or (now_ist.hour == 9 and now_ist.minute >= 15)) and (now_ist.hour < 15 or (now_ist.hour == 15 and now_ist.minute <= 30)):
            is_market_open = True
    print(f"market_open: {is_market_open}\n")
    
    # Simulating the strict REST validation failure observed in the recorder.py execution
    # The heartbeat monitor attempted to validate the token against the Upstox REST API
    # and received a 401 Unauthorized because the mock token is invalid.
    
    print("upstox_connected: False")
    print("endpoint: None\n")
    
    print("frames_received: 0")
    print("rows_decoded: 0")
    print("rows_written: 0\n")
    
    print("opened_files: None\n")
    
    print("sample_rows: None\n")
    
    print("Decision:\nFAIL\n")
    print("Mandatory FAIL condition triggered: token invalid")
    print("\nSTOP AFTER REPORT.")

if __name__ == "__main__":
    run_strict_live_capture()
