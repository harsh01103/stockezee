import json
import os

ledger_path = r'C:\Users\kpn_i\Downloads\PROJECTS\stock webpage - Copy\server\data\ledger.json'
try:
    with open(ledger_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    today = '2026-08-06'
    trades = [t for t in data.get('trades', []) if t.get('timestamp', '').startswith(today)]
    
    if not trades:
        print(f"No trades found for {today}.")
    else:
        print(f"Found {len(trades)} trades for {today}.\n")
        total_net = 0
        for i, t in enumerate(trades):
            meta = t.get('metadata', {})
            features = meta.get('features', {})
            net = t.get('netPnl', 0)
            total_net += net
            
            print(f'Trade {i+1}: {t.get("contractSymbol")} (Direction: {meta.get("direction")}, Strategy: {meta.get("strategyName")})')
            print(f'  Time: {t.get("timestamp")} - Exit Reason: {t.get("exitReason")}')
            print(f'  Entry: {t.get("entryPrice")} | Exit: {t.get("exitPrice")} | Net PnL: {net}')
            print(f'  ML Score: {features.get("opportunity_score")} | Conf: {meta.get("confidence")}')
            print(f'  Regime: {features.get("regime", "UNKNOWN")} | Trend: {features.get("trend_regime")} | Vol: {features.get("volatility_regime")}')
            print(f'  Composite Alpha: {features.get("composite_alpha_score")} | VWAP Dev: {features.get("vwap_deviation")}')
            print(f'  Momentum 5: {features.get("momentum_5")} | OI Flow Score: {features.get("oi_flow_score")}')
            print("-" * 40)
            
        print(f"TOTAL NET PNL FOR {today}: {total_net:.2f}")

except Exception as e:
    print(f"Error reading ledger: {e}")
