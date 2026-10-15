import json
import sys

def main():
    ledger_path = r'C:\Users\kpn_i\Downloads\PROJECTS\stock webpage - Copy\server\data\ledger.json'
    try:
        with open(ledger_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        today = "2026-07-23"
        trades = [t for t in data.get('trades', []) if t.get('timestamp', '').startswith(today)]
        if not trades:
            print(f"No trades found for {today}.")
            return
            
        print(f"--- Trades for {today} ---")
        for t in trades:
            print(f"Time: {t.get('timestamp')}, Symbol: {t.get('contractSymbol')}, Action: {t.get('action')}, Qty: {t.get('qty')}, Entry: {t.get('entryPrice')}, Exit: {t.get('exitPrice', 'N/A')}, Status: {t.get('status')}, PnL: {t.get('pnl', 'N/A')}")
            
    except Exception as e:
        print(f"Error reading ledger: {e}")

if __name__ == "__main__":
    main()
