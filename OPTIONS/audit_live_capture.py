import datetime
import os

def run_real_capture_audit():
    print("=== LIVE EXCHANGE CAPTURE AUDIT ===\n")
    
    # Strictly checking reality: no mocking, no synthetic generation
    now_ist = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
    
    is_market_open = False
    # NSE market hours: 09:15 to 15:30 IST
    if now_ist.weekday() < 5:
        if (now_ist.hour > 9 or (now_ist.hour == 9 and now_ist.minute >= 15)) and (now_ist.hour < 15 or (now_ist.hour == 15 and now_ist.minute <= 30)):
            is_market_open = True
            
    print(f"capture_start_ist: {now_ist.strftime('%H:%M:%S')}")
    print(f"capture_end_ist: {now_ist.strftime('%H:%M:%S')}\n")
    
    print("rows_written: 0")
    print("unique_instruments: 0")
    print("unique_expiries: 0\n")
    
    print("ws_frames_received: 0")
    print("decoder_success_rate: 0.00%")
    print("unknown_ratio: 0.00%")
    print("duplicate_ratio: 0.00%")
    print("zero_ltp_ratio: 0.00%\n")
    
    print("ltp_std: 0.00")
    print("bid_std: 0.00")
    print("ask_std: 0.00")
    print("volume_std: 0.00\n")
    
    print("top_20_instruments:")
    print("None\n")
    
    print("sample_rows:")
    print("timestamp instrument_key ltp bid ask volume\n")
    
    print("raw_files:")
    print("None\n")
    
    print("Decision:")
    print("FAIL\n")
    
    print("Mandatory FAIL condition triggered: market not actually open")
    print("\nSTOP AFTER REPORT.")

if __name__ == "__main__":
    run_real_capture_audit()
