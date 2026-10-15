# Monday Market Open Operating Guide (09:00 AM - 15:30 PM IST)

This guide walks you through starting the complete Options Platform on Monday morning during live market hours.

---

## 🏗️ Architecture: The 4 Core Services

The platform consists of **4 interconnected components**:

1. **`stock webpage - Copy\server` (`node index.js`)**: Express backend providing REST APIs for option chains, quotes, and paper trading ledger on port 4000.
2. **`stock webpage - Copy\app` (`npm run dev`)**: Vite + React frontend dashboard on port 5173.
3. **`OPTIONS` (`python recorder.py`)**: **Upstox Market Data Feed Recorder**. Connects to Upstox WebSocket V2 (Protobuf), subscribes to 62 dynamic option strikes across NIFTY & BANKNIFTY, flushes Parquet files, and streams ticks via UDP port 5005.
4. **`OPTIONS` (`python runner.py`)**: **Quant Execution Engine**. Consumes the live tick stream from `recorder.py`, computes Black-Scholes Greeks, VWOIM, Market Regime, Kelly position sizing, and outputs real-time trade signals to `reports/live_trade_ideas.csv`.

---

## ⚡ Option 1: 1-Click Startup (Recommended)

Just double-click:
📂 `c:\Harsh\StockProject\HARSH\OPTIONS!!!!!\START_OPTIONS_SYSTEM.bat`

It automatically:
1. Launches the **Backend API Server** (`localhost:4000`)
2. Launches the **Frontend Web UI** (`localhost:5173`)
3. Opens the **Upstox Morning Login** dialog in your browser
4. Prompts you to press any key after completing login
5. Launches **`recorder.py`** (Upstox WebSocket Feed)
6. Launches **`runner.py`** (Quant Engine)
7. Opens the **Live Options Dashboard**: [http://localhost:5173/#/options](http://localhost:5173/#/options)

---

## 🛠️ Option 2: Manual Terminal Startup (Step-by-Step)

If you prefer opening terminals manually, open 4 separate PowerShell or Command Prompt windows:

### Terminal 1: Backend API (8:45 AM – 9:00 AM)
```powershell
cd "c:\Harsh\StockProject\HARSH\OPTIONS!!!!!\stock webpage - Copy\server"
node index.js
```
*Output: `✅ Backend running on http://localhost:4000`*

---

### Step 2: Renew Upstox Token (Daily 1-Click Login)
> **Note:** Upstox access tokens automatically expire every day at 3:30 AM IST per SEBI exchange regulations.

1. Open your browser to:
   👉 **http://localhost:4000/login**
2. Enter your registered mobile number, OTP, and 6-digit PIN.
3. You will see: **`Upstox authentication successful!`**
4. *Both `recorder.py` and `runner.py` will automatically read and encrypt this fresh token.*

---

### Terminal 2: Frontend Web UI
```powershell
cd "c:\Harsh\StockProject\HARSH\OPTIONS!!!!!\stock webpage - Copy\app"
npm run dev
```
*Output: `Local: http://localhost:5173/`*

---

### Terminal 3: Upstox Feed Recorder (`recorder.py`)
```powershell
cd "c:\Harsh\StockProject\HARSH\OPTIONS!!!!!\OPTIONS"
python recorder.py
```
*Output:*
- `Upstox WebSocket Connected.`
- `Loaded 36465 F&O instruments.`
- `NSE cookies refreshed OK (curl_cffi)`
- `Universe updated: 15 NIFTY strikes, 15 BANKNIFTY strikes`
- `Sent subscription for 62 instruments.`
- `Ingress validation passed. Recorder running.`

---

### Terminal 4: Quant Execution Engine (`runner.py`)
```powershell
cd "c:\Harsh\StockProject\HARSH\OPTIONS!!!!!\OPTIONS"
python runner.py
```
*Output:*
- Global Macro Sentiment scan (Crude, VIX, S&P 500, USDINR, DAX)
- Fundamental Heavyweight scores (HDFCBANK, RELIANCE, ICICIBANK, INFY)
- `🟢 MARKET SCANNER ONLINE`
- Consuming UDP tick stream and evaluating cycles every 3 seconds

---

## 🕒 Market Session Timeline

| Time (IST) | System Activity |
| :--- | :--- |
| **08:45 – 09:00 AM** | Run launcher and complete the 1-click Upstox morning login. |
| **09:00 – 09:15 AM** | Pre-market session: System computes macro sentiment risk scores. |
| **09:15 AM** | Live Market Opens: Upstox WebSocket frames start flowing through `recorder.py`. |
| **09:15 – 09:45 AM** | Opening Range Breakout (ORB 30-min window) initialized. |
| **09:45 – 15:30 PM** | Real-time algorithmic trading: `runner.py` evaluates Momentum Breakout and Mean Reversion, firing signals when confidence $\ge 0.70$. |
| **15:30 – 15:40 PM** | Intraday auto-square off and extended session close. |
| **15:40 PM** | `runner.py` logs total signals, winners/losers, and cleanly terminates for the day. |

---

## 🖥️ Live Monitoring URLs

- **Options Chain & Live Greeks**: [http://localhost:5173/#/options](http://localhost:5173/#/options)
- **Virtual Paper Trading & Ledger**: [http://localhost:5173/#/demo](http://localhost:5173/#/demo)
- **Backend Health Check**: [http://localhost:4000/monitoring/health](http://localhost:4000/monitoring/health)
- **Live Signals File**: `OPTIONS/reports/live_trade_ideas.csv`
- **Watchdog Heartbeat**: `OPTIONS/reports/heartbeat.txt`
