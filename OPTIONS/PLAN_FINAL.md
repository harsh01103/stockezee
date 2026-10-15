## 1. System Overview

This document is the **complete technical specification** for an automated options trading system on Nifty & Bank Nifty.  
It contains:

- A **real‑time market regime detector** that classifies every minute of the session.  
- **Two independent strategies**: Momentum Breakout (for trending / momentum‑burst markets) and Mean‑Reversion (for range‑bound markets).  
- **Full signal selection rules**, especially for multiple strikes on the same index.  
- **Exact position sizing, risk caps, and exit logic** tailored to a ₹1,00,000 account with ~₹10,000 deployed per trade.  
- **Implementation details** for data fetching, indicator calculation, and order placement via Upstox free API.

All indicators are computed locally. No paid data feeds or external services are required.

---

## 2. System Architecture & State Machine

```
┌─────────────────────────────────────────────────┐
│          MASTER LOOP (every 15 min)              │
│  Reclassify Regime & adjust active strategy     │
└─────────────────────┬───────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │     REGIME DETECTOR       │
        │ (ADX, Trend Persistence,  │
        │  Breakout Success, VWAP)  │
        └─────────────┬─────────────┘
                      │
    ┌─────────────────┼─────────────────┐
    ▼                 ▼                  ▼
🟢 TREND          🟡 MOM_BURST       🟠 RANGE      🔴 WHIPSAW
    │                 │                  │               │
    ▼                 ▼                  ▼               ▼
Strategy A       Strategy A          Strategy B     Safety Mode
(full size,      (reduced          (fade ORB      (no new trades,
 runner to T2)   aggression,       extremes)      or 0.4× size
                  book 100% at T1)                with tight caps)
```

**Key State Variable:** `current_regime` is stored and can be updated at each 15‑minute checkpoint. If the regime changes from RANGE to TREND, we immediately switch strategies. All pending orders of the old strategy are cancelled before switching.

**Regime Persistence:** A regime must hold for at least **10 minutes** before a switch is triggered, to avoid flipping on noise.

---

## 3. Market Type Detector – Full Specification

### 3.1 Required Data

| Data | Source | Interval | Purpose |
|------|--------|----------|---------|
| Candles (OHLCV) | Upstox Historical API | 1‑min, 5‑min, 15‑min | ADX, ATR, VWAP, EMA, ORB |
| Real‑time quote | Upstox WebSocket / Quote API | Tick | VWAP cross detection (but we use 1‑min close for regime, tick for entry) |
| India VIX | Upstox / NSE | Once | Sizing |

**Note:** For regime decisions we use **15‑min candles** for ADX, and **5‑min candles** for Trend Persistence, VWAP crosses, and ATR. The Opening Range (ORB) is computed from the first 30 minutes of 1‑min candles (9:15–9:45).

### 3.2 Indicator Computations (pandas‑ta)

```python
import pandas as pd
import pandas_ta as ta

def compute_regime_indicators(df_1m, df_5m, df_15m):
    # ADX on 15-min
    adx_df = ta.adx(df_15m['high'], df_15m['low'], df_15m['close'], length=14)
    last_adx = adx_df['ADX_14'].iloc[-1]

    # ATR on 5-min
    atr_5m = ta.atr(df_5m['high'], df_5m['low'], df_5m['close'], length=14).iloc[-1]

    # VWAP on 5-min for regime (cumulative)
    df_5m['vwap'] = (df_5m['close'] * df_5m['volume']).cumsum() / df_5m['volume'].cumsum()
    
    # EMA 9 on 5-min
    df_5m['ema9'] = ta.ema(df_5m['close'], length=9)

    # Trend Persistence: consecutive 5-min candles close > EMA9 and close > VWAP
    # We'll count current run
    # ... (implementation later)

    # Breakout Success Rate: track over first 5 breakouts after ORB
    # We'll maintain a counter of successes.

    return last_adx, atr_5m, df_5m[['vwap','ema9']]
```

### 3.3 Detection Logic (Pseudocode)

```python
def determine_regime(last_adx, trend_persistence_minutes, breakout_success_rate, vwap_crosses_last_hour, orb_intact, expiry_day, time_now):
    if expiry_day and time_now.time() >= time(14,0):
        # Override
        if current_regime == TREND: return MOMENTUM_BURST
        if current_regime == RANGE: return WHIPSAW

    # TREND
    if last_adx > 25 and trend_persistence_minutes >= 20 and vwap_crosses_last_hour == 0:
        return TREND
    # MOMENTUM BURST
    if (last_adx >= 18) and (vwap_crosses_last_hour in [2,3] or (last_adx > 25 and trend_persistence_minutes < 20)):
        return MOMENTUM_BURST
    # RANGE
    if (last_adx < 18) or (breakout_success_rate <= 0.3 and orb_intact) or (vwap_crosses_last_hour > 3 and not atr_expanding):
        return RANGE
    # WHIPSAW
    return WHIPSAW
```

**Trend Persistence Calculation:**

- Start from the current 5‑min candle.
- Look backwards: count how many consecutive 5‑min candles (including current) close above 9‑EMA **and** close above VWAP.
- Multiply by 5 to get minutes. If >= 20, persistent.

**Breakout Success Rate Calculation:**

- After 9:45, record every breakout attempt: when price crosses above ORB high or below ORB low.
- For the first 5 such events, mark a “success” if price stays outside the range for at least 5 consecutive minutes.
- Success rate = (successes / 5).

**VWAP Cross Counter:**

- Over the last 12 five‑min candles (1 hour), count how many times price crossed from above to below or vice versa.

**ORB Intact:** If price has not broken ORB boundaries by more than 0.3% in the last 30 minutes, ORB is intact.

---

## 4. Signal Processing & Concurrency Management  
*(This section directly answers “what if same underlying and same condition like nifty 23550 CE and 23300 CE”)*

### 4.1 The Core Rule

**We never hold more than one directional position on the same underlying at the same time.**  
This is to avoid correlated risk that amplifies drawdowns. If multiple signals arrive for the same index (e.g., Nifty), we must **select the best one** and discard the others.

### 4.2 Multiple Signal Handling for the Same Underlying

When two or more entry signals fire **within the same 60‑second window** for different strikes of the same index, we rank them using the following weighted scoring system and trade only the highest‑ranked signal.

**Selection Score Formula:**

```
score = (0.30 * confidence) 
      + (0.20 * execution_score) 
      + (0.20 * liquidity_score) 
      + (0.15 * delta_quality) 
      + (0.10 * spread_pct_score) 
      + (0.05 * oi_density_score)
```

Where each sub‑score is normalised 0‑1 relative to the candidates.

- **confidence:** Already in telemetry.  
- **execution_score:** Already in telemetry.  
- **liquidity_score:** Min(1.0, `(bid_size + ask_size) / average_volume_per_minute`). (If volume data missing, use `oi_density` as proxy.)  
- **delta_quality:**  
  - For trend/momentum longs, we prefer delta between 0.5 and 0.8 (gives good participation without excessive cost).  
  - Score = 1.0 – abs(delta – 0.65) / 0.3, clamped 0‑1.  
- **spread_pct_score:** 1.0 – (spread/mid_price) / 0.02, clamped 0‑1.  
- **oi_density_score:** Min(1.0, oi_density * 10). (Higher OI density = more liquid.)

If there is a tie, the strike with the higher **execution score** wins.

**Exception:** If a signal arrives **after** we already have an open position on the same underlying (even if the existing position is in profit), we do **not** take the new signal. The existing trade must fully exit before a new entry on the same underlying.

### 4.3 Concurrent Positions Across Underlyings

We allow a maximum of **2 concurrent positions** system‑wide, but they must be on **different underlyings** (e.g., one Nifty, one BankNifty).  
If we already have one Nifty position open, and a BankNifty signal fires, we can take it, provided total system risk does not exceed 3% of account (i.e., combined potential loss ≤ ₹3,000). If combined risk would exceed this, we skip the second signal.

### 4.4 Signal Expiry and Queuing

- Every signal has a `valid_until = signal_timestamp + 60 seconds`. If not filled by then, it is cancelled.
- If a new signal for the same underlying arrives while the first signal’s order is still pending, we **cancel the old order** and re‑evaluate the new signal against the ranking rules above.
- There is no queuing; only the currently highest‑ranked active signal is sent to the broker.

---

## 5. Strategy A – Momentum Breakout (Detailed)

### 5.1 Entry Filter Pipeline

Each filter returns `PASS` or `FAIL`. If any filter returns `FAIL`, the signal is skipped. The filters are applied in the order listed.

1. **ba_press contribution cap**  
   ```python
   if sig['feature_contributions']['ba_press'] > 0.8:
       confirmers = ['vol_burst','ema_cross','oi_accel']
       if sum(sig['feature_contributions'][k] > 0 for k in confirmers) < 2:
           return FAIL
   ```

2. **Trend alignment**  
   ```python
   if sig['direction'] == 'BULLISH':
       if sig['features']['ema_cross_pct'] <= 0 or sig['features']['mid_price'] <= sig['features']['vwap']:
           return FAIL
   # else for BEARISH opposite
   ```

3. **Smart RSI** (only for longs)  
   ```python
   if sig['direction'] == 'BULLISH':
       if (sig['features']['rsi_14'] > 75 
           and sig['features']['mid_price'] > sig['features']['vwap'] * 1.005
           and current_atr < previous_atr):  # ATR falling (compare 5-min ATR to its prior value)
           return FAIL
   ```

4. **Spread filter**  
   ```python
   if sig['metadata']['bidAskSpread'] / sig['features']['mid_price'] > 0.015:
       return FAIL  # or could decide to skip only if size large, but we just fail
   ```

5. **Deep ITM expiry ban**  
   ```python
   if is_expiry_day and sig['metadata']['delta'] > 0.95:
       return FAIL
   ```

6. **ORB gate (time‑bound)**  
   ```python
   now = get_current_time()
   if now < time(10,30):
       if sig['direction'] == 'BULLISH' and spot_price <= orb_high:
           return FAIL
       if sig['direction'] == 'BEARISH' and spot_price >= orb_low:
           return FAIL
   ```

7. **Multi‑timeframe**  
   Get latest 15‑min candle.  
   ```python
   if sig['direction'] == 'BULLISH' and not (candle_close > candle_open and candle_close > candle_mid):
       return FAIL
   ```

8. **Signal decay**  
   ```python
   if (now - sig['metadata']['signalTimestamp']).total_seconds() > 30:
       cancel_order(); return FAIL
   ```

### 5.2 Position Sizing & Risk Cap

Always trade 1 lot (65 Nifty, 30 BankNifty) unless capped by risk.

- **Risk per trade (RPT):** `(entry_price - stop_loss) * lotSize` for longs (absolute for shorts).
- **Max allowed RPT:** ₹1,500 (1.5% of ₹1L).  
  If RPT > 1500, we can either:
  - Use a tighter stop (e.g., 1.0 × ATR instead of 1.5), recalculate RPT. If still >1500, skip trade.
  - Or skip immediately.

- **Scaling multipliers (ambition, not size):**  
  - Trend: target T2 for runner.  
  - Momentum Burst: target T1 only, no runner.

We never increase beyond 1 lot. The size is fixed; risk is controlled by entry/stop placement.

### 5.3 Execution & Exit Details

- **Entry order:** Limit order at `limitPrice` (from signal) or better, until maxEntry.  
- **Stop‑loss order:** Immediately after fill, place a **stop‑limit** order: trigger = stopLoss, limit = trigger * (1 - 0.01) for longs (or trigger * (1 + 0.01) for shorts). This gives a 1% buffer.  
  - If the stop‑limit is not filled within 3 seconds of trigger, cancel and re‑submit as a market order? Better to avoid market; we can widen the limit slightly and retry. System logs the event.  
- **ATR‑based stop override:** If the signal’s proposed stop is wider than 1.5 × ATR(14,5m) from entry, we **tighten** it to exactly 1.5 × ATR, provided the new stop is not less than 0.75R away (to avoid too tight). If it would be less than 0.75R, we skip the trade (risk‑reward too poor).

**Profit Management:**

- At Target 1: sell 50% of position (or 33 shares for Nifty, 15 for BankNifty – round down to lot size multiples). Move stop on remaining to entry (breakeven).  
- If price reaches 0.75R profit but hasn’t yet hit T1, activate trailing stop: new stop = max(current stop, current price – 0.25R). Update every 1 minute.  
- Hard time stop: after `holdTime` max seconds (e.g., 8 min), if trade not closed, exit at market with limit offset.

**GTT disaster stop:** After entry, place a GTT order with trigger 20% away from entry. Cancel on normal exit.

### 5.4 Handling Partial Fill and Rejection

If only a portion of the 1 lot is filled (unlikely with options on liquid strikes), we treat the position as active with filled quantity and adjust stops proportionally. If fill fails entirely within 60 seconds, cancel and log.

---

## 6. Strategy B – Mean‑Reversion (Range Regime)

This strategy only runs when `current_regime == RANGE`.

### 6.1 Signal Generation

We do **not** rely on the existing momentum signals. Instead, we monitor price relative to ORB boundaries:

- **Long trigger:** `spot_price <= orb_low * 1.002` (within 0.2%) and RSI(14,5m) < 30 and `vwap/price - 1 > 0.003` (price is 0.3% below VWAP).  
- **Short trigger:** `spot_price >= orb_high * 0.998` and RSI > 70 and `price/vwap - 1 > 0.003`.

Both triggers only active after 10:30 AM.

When a trigger fires, we immediately place a limit order at the boundary price (orb_low for long, orb_high for short). The order is valid for 2 minutes. If not filled, cancel.

### 6.2 Option Selection for the Fade

We need to choose a liquid ATM or slightly OTM option in the direction of the fade:

- **Long (bullish fade):** Buy a **Call** with delta between 0.3–0.5, expiry same day, preferably with tight spread.
- **Short (bearish fade):** Buy a **Put** with delta –0.3 to –0.5.

Use a selection algorithm similar to the momentum strike selection, prioritising liquidity and spread.

### 6.3 Exit & Sizing

- **Target:** When price returns to VWAP (or a fixed 0.6R reward). If price touches VWAP, exit 50%; move stop to entry; rest at opposite ORB boundary.
- **Stop:** If price moves beyond the boundary by 0.2% (i.e., orb_low * 0.998 for longs, orb_high * 1.002 for shorts), exit immediately with stop‑limit.
- **Time stop:** 20 minutes.
- **Sizing:** 1 lot. Risk per trade (`stop distance * lotSize`) must be ≤ ₹750. If not, skip.

---

## 7. Safety Mode – Whipsaw Handling

- No new trades are initiated.
- If we have an open position from earlier (e.g., from before regime changed to WHIPSAW), manage it with existing stops, but do not add.
- Optional: If a momentum signal has `opportunity_score > 75` and at least 3 feature confirmers, we may take the trade but with **0.4× aggression**:  
  - Use stop = 1.2 × ATR (tighter)  
  - Exit 100% at T1, no runner  
  - Risk cap = ₹600 per trade

---

## 8. Risk & Account Management (Global)

- **Daily loss limit:** Track cumulative net P&L for the day. If it falls below –3% of account (₹3,000), cancel all orders and stop trading.  
- **Profit lock:**  
  - If daily net P&L reaches +3% (₹3,000), change daily loss limit to –1% (‑₹1,000).  
  - If daily net P&L reaches +5% (₹5,000), close all open positions and disable new trades for the day.  
- **Consecutive loss drawdown:** After 3 consecutive losing trades (any strategy), reduce risk per trade by skipping trades unless `confidence > 0.65` (momentum) or RSI extreme (range).  
- **Total portfolio heat:** Sum of (entry–stop)*qty for all open positions must be < ₹2,000 at any time. If a new trade would exceed this, it is skipped.  
- **All exits** use stop‑limit orders; no market orders for stop losses.

---

