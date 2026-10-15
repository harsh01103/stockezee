import json

ledger_path = r'C:\Users\kpn_i\Downloads\PROJECTS\stock webpage - Copy\server\data\ledger.json'
with open(ledger_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

today = '2026-07-23'
trades = [t for t in data.get('trades', []) if t.get('timestamp', '').startswith(today)]
print(f'Total trades today: {len(trades)}')

total_net = 0
for i, t in enumerate(trades):
    meta = t.get('metadata', {})
    features = meta.get('features', {})
    net = t.get('netPnl', 0)
    total_net += net
    
    print(f'\n{"="*60}')
    print(f'Trade {i+1}: {t.get("contractSymbol")}')
    print(f'  Timestamp:     {t.get("timestamp")}')
    print(f'  Direction:     {meta.get("direction")}')
    print(f'  Entry / Exit:  {t.get("entryPrice")} / {t.get("exitPrice")}')
    print(f'  Gross PnL:     {t.get("grossPnl")}')
    print(f'  Net PnL:       {net}')
    print(f'  Exit Reason:   {t.get("exitReason")}')
    print(f'  Confidence:    {meta.get("confidence")}')
    print(f'  Strategy:      {meta.get("strategyName")}')
    print(f'  --- ML Features ---')
    print(f'  Regime:            {features.get("regime", "UNKNOWN")}')
    print(f'  Volatility Regime: {features.get("volatility_regime")}')
    print(f'  Trend Regime:      {features.get("trend_regime")}')
    print(f'  Volume Regime:     {features.get("volume_regime")}')
    print(f'  RSI 14:            {features.get("rsi_14")}')
    print(f'  Opportunity Score: {features.get("opportunity_score")}')
    print(f'  Composite Alpha:   {features.get("composite_alpha_score")}')
    print(f'  VWAP Deviation:    {features.get("vwap_deviation")}')
    print(f'  Momentum 5:        {features.get("momentum_5")}')
    print(f'  BB %B:             {features.get("bb_pct_b")}')
    print(f'  Compression:       {features.get("compression_score")}')
    print(f'  Regime Confidence: {features.get("regime_confidence")}')
    print(f'  IB High:           {features.get("ib_high")}')
    print(f'  IB Low:            {features.get("ib_low")}')
    print(f'  EMA Cross:         {features.get("ema_cross_pct")}')
    print(f'  VWOIM:             {features.get("vwoim")}')
    print(f'  OI Flow Score:     {features.get("oi_flow_score")}')
    print(f'  Direction Signal:  {features.get("direction")}')

print(f'\n{"="*60}')
print(f'TOTAL NET PnL: {total_net:.2f}')
