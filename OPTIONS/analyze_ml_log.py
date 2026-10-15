import json

# Read ML features log
log_path = r'reports\ml_features_log.jsonl'
with open(log_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

today = '2026-07-23'
signals = [json.loads(l) for l in lines if today in l]
print(f'Total signals logged today: {len(signals)}')

for i, s in enumerate(signals):
    ts = s.get('timestamp', '')
    print(f'\n{"="*60}')
    print(f'Signal {i+1}: {s.get("target_contract")} at {ts}')
    print(f'  Action:        {s.get("action")}')
    print(f'  Direction:     {s.get("direction", "N/A")}')
    print(f'  Regime:        {s.get("regime")}')
    print(f'  Confidence:    {s.get("confidence")}')
    print(f'  Limit Price:   {s.get("limit_price")}')
    print(f'  Stop Loss:     {s.get("stop_loss")}')
    print(f'  --- Key Features ---')
    print(f'  volatility_regime:  {s.get("volatility_regime")}')
    print(f'  trend_regime:       {s.get("trend_regime")}')
    print(f'  volume_regime:      {s.get("volume_regime")}')
    print(f'  compression_score:  {s.get("compression_score")}')
    print(f'  regime_confidence:  {s.get("regime_confidence")}')
    print(f'  is_trending:        {s.get("is_trending")}')
    print(f'  rsi_14:             {s.get("rsi_14")}')
    print(f'  ema_cross_pct:      {s.get("ema_cross_pct")}')
    print(f'  vwap_deviation:     {s.get("vwap_deviation")}')
    print(f'  momentum_5:         {s.get("momentum_5")}')
    print(f'  bb_pct_b:           {s.get("bb_pct_b")}')
    print(f'  opportunity_score:  {s.get("opportunity_score")}')
    print(f'  composite_alpha:    {s.get("composite_alpha_score")}')
    print(f'  oi_flow_score:      {s.get("oi_flow_score")}')
    print(f'  spot (underlying):  {s.get("spot")}')
    print(f'  ib_high:            {s.get("ib_high", "N/A")}')
    print(f'  ib_low:             {s.get("ib_low", "N/A")}')
    print(f'  pcr:                {s.get("pcr")}')
    print(f'  dpcr_dt:            {s.get("dpcr_dt")}')
    print(f'  selected_delta:     {s.get("selected_delta")}')
    print(f'  selected_iv:        {s.get("selected_iv")}')
    print(f'  fair_price:         {s.get("fair_price")}')
    print(f'  fair_value_gap:     {s.get("fair_value_gap")}')
    
    # Check execution components
    exec_comp = s.get('execution_score_components', {})
    if exec_comp:
        print(f'  --- Execution Score Components ---')
        for k,v in exec_comp.items():
            print(f'    {k}: {v}')
