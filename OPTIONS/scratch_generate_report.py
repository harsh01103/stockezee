import json
import statistics
from datetime import datetime
import os

ledger_path = r'c:\Users\kpn_i\Downloads\PROJECTS\stock webpage - Copy\server\data\ledger.json'
with open(ledger_path, encoding='utf-8') as f:
    data = json.load(f)

# Filter for trades from 2026-06-29 to 2026-07-01
trades = data.get('trades', [])
recent_trades = []
for t in trades:
    # timestamp looks like "2026-06-29T10:15:00Z"
    ts_str = t.get('timestamp', '')
    if ts_str.startswith('2026-06-29') or ts_str.startswith('2026-06-30') or ts_str.startswith('2026-07-01'):
        recent_trades.append(t)

closed = [t for t in recent_trades if t.get('status') == 'CLOSED']

# Separate winners and losers
winners = [t for t in closed if (t.get('netPnl') or t.get('pnl') or 0) > 0]
losers = [t for t in closed if (t.get('netPnl') or t.get('pnl') or 0) <= 0]
total_closed = len(closed)

total_pnl = sum((t.get('netPnl') or t.get('pnl') or 0) for t in closed)

report = []
report.append("# New Strategy 3-Day Journey Report (June 29 - July 1, 2026)\n")
report.append("## Overview\n")
report.append(f"- **Total Trades Executed**: {total_closed}")
report.append(f"- **Winners**: {len(winners)}")
report.append(f"- **Losers**: {len(losers)}")
wr = len(winners)/total_closed*100 if total_closed > 0 else 0
report.append(f"- **Win Rate**: {wr:.1f}%")
report.append(f"- **Net PnL**: {total_pnl:+.2f}\n")

if total_closed > 0:
    # 1. CONFIDENCE
    report.append("## 1. Confidence Analysis")
    w_conf = [t['metadata'].get('confidence', 0) for t in winners if 'metadata' in t and t['metadata'].get('confidence')]
    l_conf = [t['metadata'].get('confidence', 0) for t in losers if 'metadata' in t and t['metadata'].get('confidence')]
    if w_conf: report.append(f"- **Winner avg confidence**: {statistics.mean(w_conf):.4f} (Range: {min(w_conf):.4f} - {max(w_conf):.4f})")
    if l_conf: report.append(f"- **Loser avg confidence**: {statistics.mean(l_conf):.4f} (Range: {min(l_conf):.4f} - {max(l_conf):.4f})")
    
    report.append("\n| Threshold | Winners | Losers | Win Rate |")
    report.append("|-----------|---------|--------|----------|")
    for threshold in [0.65, 0.67, 0.70, 0.72, 0.75]:
        w = len([t for t in winners if 'metadata' in t and (t['metadata'].get('confidence') or 0) >= threshold])
        l = len([t for t in losers if 'metadata' in t and (t['metadata'].get('confidence') or 0) >= threshold])
        total = w + l
        t_wr = w/total*100 if total > 0 else 0
        report.append(f"| >= {threshold} | {w} | {l} | {t_wr:.1f}% |")

    # 2. UNDERLYING
    report.append("\n## 2. Underlying Asset Analysis")
    report.append("| Underlying | Winners | Losers | Win Rate | Net PnL |")
    report.append("|------------|---------|--------|----------|---------|")
    for underlying in ['NIFTY', 'BANKNIFTY']:
        w = [t for t in winners if t.get('underlying') == underlying or (underlying in t.get('contractSymbol', ''))]
        l = [t for t in losers if t.get('underlying') == underlying or (underlying in t.get('contractSymbol', ''))]
        total = len(w) + len(l)
        t_wr = len(w)/total*100 if total > 0 else 0
        w_pnl = sum(t.get('netPnl') or t.get('pnl') or 0 for t in w)
        l_pnl = sum(t.get('netPnl') or t.get('pnl') or 0 for t in l)
        report.append(f"| {underlying} | {len(w)} | {len(l)} | {t_wr:.1f}% | {w_pnl+l_pnl:+.2f} |")

    # 3. SIDE
    report.append("\n## 3. Direction (CE vs PE)")
    report.append("| Side | Winners | Losers | Win Rate | Net PnL |")
    report.append("|------|---------|--------|----------|---------|")
    for side in ['CE', 'PE']:
        w = [t for t in winners if t.get('side') == side or (t.get('contractSymbol','').endswith(side))]
        l = [t for t in losers if t.get('side') == side or (t.get('contractSymbol','').endswith(side))]
        total = len(w) + len(l)
        t_wr = len(w)/total*100 if total > 0 else 0
        w_pnl = sum(t.get('netPnl') or t.get('pnl') or 0 for t in w)
        l_pnl = sum(t.get('netPnl') or t.get('pnl') or 0 for t in l)
        report.append(f"| {side} | {len(w)} | {len(l)} | {t_wr:.1f}% | {w_pnl+l_pnl:+.2f} |")

    # 5. TIME OF DAY
    report.append("\n## 4. Time of Day (IST)")
    report.append("| Hour | Winners | Losers | Win Rate | Net PnL |")
    report.append("|------|---------|--------|----------|---------|")
    for start_h, end_h, label in [(9,10,'09-10'),(10,11,'10-11'),(11, 12, '11-12'), (12, 13, '12-13'), (13, 14, '13-14'), (14, 15, '14-15'),(15,16,'15-16')]:
        w, l = [], []
        for t in closed:
            ts_str = t.get('timestamp')
            if not ts_str: continue
            try:
                hour = datetime.fromisoformat(ts_str.replace('Z','+00:00')).hour
            except: continue
            if start_h <= hour < end_h:
                if (t.get('netPnl') or t.get('pnl') or 0) > 0: w.append(t)
                else: l.append(t)
        total = len(w) + len(l)
        if total > 0:
            t_wr = len(w)/total*100
            w_pnl = sum(t.get('netPnl') or t.get('pnl') or 0 for t in w)
            l_pnl = sum(t.get('netPnl') or t.get('pnl') or 0 for t in l)
            report.append(f"| {label} | {len(w)} | {len(l)} | {t_wr:.1f}% | {w_pnl+l_pnl:+.2f} |")
            
    # FEATURE ANALYSIS
    report.append("\n## 5. Feature Analysis (Key Differentiators)")
    w_feat = [t for t in winners if 'metadata' in t and t['metadata'].get('features')]
    l_feat = [t for t in losers if 'metadata' in t and t['metadata'].get('features')]
    
    if w_feat and l_feat:
        all_keys = set()
        for t in w_feat + l_feat:
            all_keys.update(t['metadata']['features'].keys())
        
        diffs = []
        for key in sorted(all_keys):
            w_vals = [t['metadata']['features'].get(key, 0) for t in w_feat if t['metadata']['features'].get(key) is not None and isinstance(t['metadata']['features'].get(key), (int, float))]
            l_vals = [t['metadata']['features'].get(key, 0) for t in l_feat if t['metadata']['features'].get(key) is not None and isinstance(t['metadata']['features'].get(key), (int, float))]
            if w_vals and l_vals:
                w_avg = statistics.mean(w_vals)
                l_avg = statistics.mean(l_vals)
                pct_diff = abs(w_avg - l_avg) / abs(l_avg) * 100 if l_avg != 0 else (100 if w_avg != 0 else 0)
                diffs.append((key, w_avg, l_avg, pct_diff))
        
        diffs.sort(key=lambda x: x[3], reverse=True)
        report.append("| Feature | Winner Avg | Loser Avg | Difference % |")
        report.append("|---------|------------|-----------|--------------|")
        for key, w_avg, l_avg, pct in diffs[:15]:
            report.append(f"| `{key}` | {w_avg:.4f} | {l_avg:.4f} | {pct:.1f}% |")

out_path = r'C:\Users\kpn_i\.gemini\antigravity-ide\brain\901460b8-2e94-4e1c-98d6-a50e7058c75e\strategy_3_day_journey.md'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(report))
print(f"Report written to {out_path}")
