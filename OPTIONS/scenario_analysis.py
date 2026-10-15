import json
from datetime import datetime, timedelta

with open(r"C:\Users\kpn_i\Downloads\PROJECTS\stock webpage - Copy\server\data\ledger.json", "r", encoding="utf-8") as f:
    data = json.load(f)

trades = data["trades"]
target_days = ["2026-06-29", "2026-06-30", "2026-07-01"]

# June 29 analysis
print("=== JUNE 29: ALL-CE DAY ANALYSIS ===")
day_trades = []
for t in trades:
    ts = t.get("timestamp", "")
    if not ts: continue
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except: continue
    if dt.strftime("%Y-%m-%d") == "2026-06-29":
        t["_dt"] = dt
        day_trades.append(t)
day_trades.sort(key=lambda x: x["_dt"])

print("Chronological trades:")
running = 0
for i, t in enumerate(day_trades):
    np_ = t.get("netPnl", 0) or 0
    running += np_
    conf = t.get("metadata", {}).get("confidence", 0) or 0
    side = t.get("side", "")
    strike = t.get("strike", 0)
    und = t.get("underlying", "")
    time_str = t["_dt"].strftime("%H:%M")
    print(f"  Trade {i+1}: {time_str} {und} {strike} {side} Conf={conf:.2f} Net={np_:+.0f} Running={running:+.0f}")

# COMBINED SCENARIO across all 3 days
print("\n=== COMBINED BEST SCENARIO (all 3 days) ===")
grand_total = 0
grand_actual = 0
for day in target_days:
    day_trades = []
    for t in trades:
        ts = t.get("timestamp", "")
        if not ts: continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except: continue
        if dt.strftime("%Y-%m-%d") == day:
            t["_dt"] = dt
            day_trades.append(t)
    day_trades.sort(key=lambda x: x["_dt"])
    
    # Combined: conf>=0.65 + 2-consec-loss adaptive cooldown (10min + conf>=0.68 to resume)
    net = 0
    streak = 0
    cooldown_until = None
    taken = 0
    for t in day_trades:
        dt = t["_dt"]
        np_ = t.get("netPnl", 0) or 0
        conf = t.get("metadata", {}).get("confidence", 0) or 0
        
        # Base filter
        if conf < 0.65:
            continue
            
        # Cooldown check
        if cooldown_until and dt < cooldown_until:
            continue
        elif cooldown_until and dt >= cooldown_until:
            if conf < 0.68:
                continue
            cooldown_until = None
            streak = 0
        
        net += np_
        taken += 1
        if np_ < 0:
            streak += 1
            if streak >= 2:
                cooldown_until = dt + timedelta(minutes=10)
        else:
            streak = 0
            cooldown_until = None
    
    actual = sum(t.get("netPnl", 0) or 0 for t in day_trades)
    grand_actual += actual
    grand_total += net
    print(f"{day}: Actual={actual:+.0f} -> Combined={net:+.0f} ({taken} trades)")

print(f"\nGRAND TOTAL: Actual={grand_actual:+.0f} -> Combined={grand_total:+.0f}")
