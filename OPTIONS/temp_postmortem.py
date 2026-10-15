import json
from datetime import datetime

with open(r'C:\Users\kpn_i\Downloads\PROJECTS\stock webpage - Copy\server\data\ledger.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

trades = [t for t in data.get('trades', []) if t.get('timestamp', '').startswith('2026-08-06')]

for i, t in enumerate(trades):
    meta = t.get('metadata', {})
    feat = meta.get('features', {})
    entry_ts = t.get('timestamp', '')
    exit_ts = t.get('exitTimestamp', '')
    
    entry_t = entry_ts.split('T')[1].split('.')[0] if 'T' in entry_ts else ''
    exit_t = exit_ts.split('T')[1].split('.')[0] if exit_ts and 'T' in exit_ts else ''
    
    hold_secs = 0
    if entry_ts and exit_ts:
        try:
            e1 = datetime.fromisoformat(entry_ts)
            e2 = datetime.fromisoformat(exit_ts)
            hold_secs = int((e2 - e1).total_seconds())
        except:
            pass
    
    sym = t.get('contractSymbol', '')
    direction = meta.get('direction', '')
    strategy = meta.get('strategyName', '')
    entry_p = t.get('entryPrice', 0)
    exit_p = t.get('exitPrice', 0)
    net_pnl = t.get('netPnl', 0)
    cap = t.get('capitalDeployed', 0)
    roc = (net_pnl / cap * 100) if cap else 0
    exit_reason = t.get('exitReason', '')
    conf = meta.get('confidence', 0)
    opp_score = feat.get('opportunity_score', 0)
    comp_alpha = feat.get('composite_alpha_score', 0)
    oi_flow = feat.get('oi_flow_score', 0)
    vwap_dev = feat.get('vwap_deviation', 0)
    mom5 = feat.get('momentum_5', 0)
    regime = feat.get('regime', '')
    vol_regime = feat.get('volatility_regime', '')
    trend = feat.get('trend_regime', '')
    
    print(f"Trade {i+1}: {sym}")
    print(f"  Direction: {direction} | Strategy: {strategy}")
    print(f"  Entry: Rs.{entry_p} @ {entry_t} | Exit: Rs.{exit_p} @ {exit_t}")
    print(f"  Hold Time: {hold_secs}s ({hold_secs//60}m {hold_secs%60}s)")
    print(f"  Net PnL: Rs.{net_pnl:.2f} | Capital: Rs.{cap:.2f} | ROC: {roc:.2f}%")
    print(f"  Exit Reason: {exit_reason}")
    print(f"  Confidence: {conf} | Opp Score: {opp_score}")
    print(f"  Composite Alpha: {comp_alpha} | OI Flow: {oi_flow}")
    print(f"  VWAP Dev: {vwap_dev} | Momentum5: {mom5}")
    print(f"  Regime: {regime} | Vol: {vol_regime} | Trend: {trend}")
    print()

print("=" * 60)
print("SUMMARY")
print("=" * 60)
total_pnl = sum(t.get('netPnl', 0) for t in trades)
total_cap = sum(t.get('capitalDeployed', 0) for t in trades)
wins = [t for t in trades if t.get('netPnl', 0) > 0]
losses = [t for t in trades if t.get('netPnl', 0) <= 0]
print(f"Total Trades: {len(trades)} | Wins: {len(wins)} | Losses: {len(losses)}")
print(f"Total PnL: Rs.{total_pnl:.2f} | Total Capital: Rs.{total_cap:.2f}")
print(f"Day ROC: {(total_pnl/total_cap)*100:.2f}%")
print(f"Win Rate: {len(wins)/len(trades)*100:.0f}%")
if wins:
    print(f"Avg Win: Rs.{sum(t.get('netPnl',0) for t in wins)/len(wins):.2f}")
if losses:
    print(f"Avg Loss: Rs.{sum(t.get('netPnl',0) for t in losses)/len(losses):.2f}")

# Check trade timing gaps
print()
print("=" * 60)
print("TRADE TIMING ANALYSIS")
print("=" * 60)
for i, t in enumerate(trades):
    entry_ts = t.get('timestamp', '')
    exit_ts = t.get('exitTimestamp', '')
    sym = t.get('contractSymbol', '')
    side = t.get('metadata', {}).get('direction', '')
    if i > 0:
        prev_exit = trades[i-1].get('exitTimestamp', '')
        try:
            gap = (datetime.fromisoformat(entry_ts) - datetime.fromisoformat(prev_exit)).total_seconds()
            print(f"  Gap between Trade {i} exit -> Trade {i+1} entry: {int(gap)}s ({int(gap)//60}m)")
        except:
            pass
    print(f"  Trade {i+1}: {sym} ({side})")

# Direction analysis
print()
print("=" * 60)
print("DIRECTION ANALYSIS")
print("=" * 60)
pe_trades = [t for t in trades if 'PE' in t.get('contractSymbol', '')]
ce_trades = [t for t in trades if 'CE' in t.get('contractSymbol', '')]
pe_pnl = sum(t.get('netPnl', 0) for t in pe_trades)
ce_pnl = sum(t.get('netPnl', 0) for t in ce_trades)
print(f"PE trades: {len(pe_trades)} | PnL: Rs.{pe_pnl:.2f}")
print(f"CE trades: {len(ce_trades)} | PnL: Rs.{ce_pnl:.2f}")
print(f"Nifty closed: +0.05% (essentially flat)")
print(f"BankNifty closed: +0.56% (strong bullish)")
print(f"BankNifty trades taken: 0")
