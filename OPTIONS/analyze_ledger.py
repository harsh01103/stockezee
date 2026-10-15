import json
from datetime import datetime
from collections import defaultdict

# Config
LEDGER_PATH = r"C:\Users\kpn_i\Downloads\PROJECTS\stock webpage - Copy\server\data\ledger.json"
TARGET_DAYS = ["2026-06-29", "2026-06-30", "2026-07-01"]
MAX_LOTS = 10
DAILY_MAX_LOSS = -5000

def load_data():
    with open(LEDGER_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('trades', [])

def process():
    trades = load_data()
    
    # Filter and sort
    target_trades = []
    for t in trades:
        ts_str = t.get("timestamp")
        if not ts_str: continue
        
        # Parse ISO string (handle +05:30)
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except:
            continue
            
        day_str = ts.strftime("%Y-%m-%d")
        if day_str in TARGET_DAYS:
            t["_dt"] = ts
            t["_day"] = day_str
            exit_ts_str = t.get("exitTimestamp")
            if not exit_ts_str:
                exit_ts_str = ts_str
            t["_exit_dt"] = datetime.fromisoformat(exit_ts_str.replace("Z", "+00:00"))
            target_trades.append(t)
            
    # Sort by exit time so we can track realized PnL correctly
    target_trades.sort(key=lambda x: x["_exit_dt"])
    
    results = {}
    for day in TARGET_DAYS:
        results[day] = {
            "total_trades": 0,
            "accepted_trades": 0,
            "rejected_time": 0,
            "rejected_max_loss": 0,
            "original_gross": 0.0,
            "original_net": 0.0,
            "new_gross": 0.0,
            "new_net": 0.0,
            "max_loss_hit": False,
            "daily_realized_pnl": 0.0,
            "scaled_down_trades": 0
        }

    # Group by day to simulate
    trades_by_day = defaultdict(list)
    for t in target_trades:
        trades_by_day[t["_day"]].append(t)
        
    for day in TARGET_DAYS:
        day_trades = trades_by_day[day]
        # Sort by entry time for simulating entry blocks
        day_trades.sort(key=lambda x: x["_dt"])
        
        # We need to simulate time passing. We'll maintain a list of closed trades and their exit times.
        closed_trades = []
        
        for t in day_trades:
            res = results[day]
            res["total_trades"] += 1
            res["original_gross"] += t.get("grossPnl", 0)
            res["original_net"] += t.get("netPnl", 0)
            
            # Check Time of Day
            hour = t["_dt"].hour
            minute = t["_dt"].minute
            
            if (hour == 9 and minute < 30) or hour >= 15:
                res["rejected_time"] += 1
                continue
                
            # Check Daily Max Loss (calculate realized PnL at the moment of THIS trade's entry)
            # Find all closed_trades where exit_dt <= current trade's entry dt
            realized_pnl_at_entry = sum(ct["new_net"] for ct in closed_trades if ct["_exit_dt"] <= t["_dt"])
            
            if realized_pnl_at_entry <= DAILY_MAX_LOSS:
                res["rejected_max_loss"] += 1
                res["max_loss_hit"] = True
                continue
                
            # Accept trade, apply Lot Scaling
            underlying = t.get("underlying", "")
            lot_size = 15 if "BANKNIFTY" in underlying else 25
            max_allowed_qty = MAX_LOTS * lot_size
            
            original_qty = t.get("qty", lot_size)
            if original_qty > max_allowed_qty:
                scale = max_allowed_qty / original_qty
                res["scaled_down_trades"] += 1
            else:
                scale = 1.0
                
            new_gross = t.get("grossPnl", 0) * scale
            new_net = t.get("netPnl", 0) * scale
            
            res["accepted_trades"] += 1
            res["new_gross"] += new_gross
            res["new_net"] += new_net
            
            t["new_net"] = new_net
            closed_trades.append(t)
            
            # update running total
            res["daily_realized_pnl"] = sum(ct["new_net"] for ct in closed_trades)
            
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    process()
