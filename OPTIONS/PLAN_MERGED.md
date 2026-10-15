# MERGED TRADING SYSTEM SPECIFICATION
*Structure & philosophy from PLAN_FINAL_FINAL; concrete mechanics grafted from PLAN_FINAL & PLAN_MASTER.*
*Nifty / BankNifty options, ~₹1,00,000 account, all data free & computed locally (Upstox + pandas-ta).*

---

## 1. Core Idea — Hierarchical Decision Tree

```
System Health OK?
      ↓
Market Regime (with confidence %)
      ↓
Strategy (Momentum OR Mean-Reversion)
      ↓
Original Signal (trusted)
      ↓
3–5 Sanity checks
      ↓
Trade
```

The regime detector does the heavy lifting. Once it confirms a momentum-friendly
environment at ≥70% confidence, the original signal is trusted almost as-is.
We do NOT re-filter everything — over-filtering on a 28-trade sample is curve-fitting,
which was a root cause of the original system's breakeven performance.

---

## 2. System Architecture

```
Market Data Layer
  → Indicator Engine (ADX, VWAP, ORB, ATR, EMA, RSI)
  → System Health Monitor  ── fail → SAFE MODE
  → Regime Detector (+ confidence)
  → Strategy Selector
        ├── Momentum Strategy (Strategy A)
        └── Mean-Reversion Strategy (Strategy B)
  → Execution Engine → Risk Manager → Logger / Analytics
```

---

## 3. System Health Monitor

Before ANY new order, verify:

- WebSocket connected & ticks fresh (<3s)
- Candle data complete
- Broker API healthy
- Clock synced
- Greeks available
- Positions reconciled

Any check fails → **SAFE MODE** (no new orders, manage existing positions only).

---

## 4. Regime Detector

### 4.1 Cadence
- Indicators update every minute.
- Regime recalculated **only on 5-min candle close**.
- A regime switch requires **2 consecutive 5-min evaluations** of the same new regime.

### 4.2 Metrics — computable definitions

| Metric | Calculation |
|--------|-------------|
| ADX(15m) | `pandas_ta.adx(high, low, close, length=14)` on 15-min candles |
| ATR(14,5m) | `pandas_ta.atr()` on 5-min candles |
| VWAP | `cumsum(close*volume) / cumsum(volume)` from session open |
| EMA9(5m) | `pandas_ta.ema(close, length=9)` |
| Trend Persistence | consecutive 5-min candles closing > EMA9 AND > VWAP; ×5 = minutes; ≥20 min = persistent |
| Breakout Success Rate | first 5 ORB breakout attempts after 9:45; "success" = price stays outside ORB ≥5 consecutive min; rate = successes/5 |
| VWAP Cross Counter | over last 12 five-min candles (1h), count above↔below crossings |
| ORB | High/Low of 9:15–9:45 from 1-min candles; "intact" = not broken >0.3% in last 30 min |

### 4.3 Four Regimes

| Regime | Conditions |
|--------|-----------|
| 🟢 **Trend** | ADX(15m)>25 AND persistence≥20min AND VWAP uncrossed 30min AND breakout success (last 5)≥60% |
| 🟡 **Momentum Burst** | ADX≥18 AND breakout success>50% AND VWAP crosses 2–3/hr. (Also if ADX>25 but persistence<20min) |
| 🟠 **Range** | ≥2 of: ADX<18, VWAP crosses>3/hr, breakout success≤30% |
| 🔴 **Whipsaw** | Everything else |

**Expiry override:** after 14:00 → Trend→Momentum Burst; Range→Whipsaw.

### 4.4 Confidence
Single 0–100% score from four key metrics equally weighted (ADX strength, persistence,
breakout success, VWAP behaviour).
- **Confidence ≥ 70%** → trade the regime's strategy.
- **Confidence < 70%** → no new trades.

---

## 5. Signal Handling & Strike Selection

- **One position per underlying at a time.** Max **2 concurrent**, different underlyings. Portfolio heat ≤ ₹2,000.
- Eligible strikes: **0.25 ≤ |delta| ≤ 0.85**.
- Multiple signals for the same underlying within 60s → rank by **Selection Score**, trade only the top:

```
score = 0.30*confidence
      + 0.20*execution_score
      + 0.20*liquidity_score
      + 0.15*delta_quality
      + 0.10*spread_pct_score
      + 0.05*oi_density_score
```

Where (each normalised 0–1 across candidates):
- `liquidity_score = min(1, (bid_size + ask_size) / avg_vol_per_min)`  (use oi_density proxy if volume missing)
- `delta_quality  = clamp01(1 - abs(delta - 0.65) / 0.3)`
- `spread_pct_score = clamp01(1 - (spread/mid) / 0.02)`
- `oi_density_score = min(1, oi_density * 10)`
- Tie → higher `execution_score` wins.

- A signal arriving when a position is already open on that underlying → **rejected** (no stacking).
- `valid_until = signal_ts + 60s`. If a new signal for the same underlying arrives while the old order is still pending → cancel old, re-rank the new one.

---

## 6. Strategy A — Momentum (Trend / Momentum Burst)

The original momentum signal is taken directly, subject ONLY to these sanity checks:

1. **Trend alignment** — Long: `ema_cross_pct>0` AND `mid>vwap`. Short: opposite.
2. **Spread check** — `(spread/mid) ≤ 0.015`.
3. **Risk check** — `(entry-stop)*lotSize ≤ ₹1,500`; if wider, **SKIP** (do not adjust the stop).
4. **Freshness** — cancel if signal older than 30s.
5. **Deep-ITM expiry ban** — skip if delta>0.95 on expiry day.

No RSI, no multi-timeframe candle, no post-10:30 ORB gate — the regime detector has
already confirmed the environment, and the original signal already embeds volume, OI,
and price action.

### Execution & profit management
- **Entry:** limit at signal's limit price, 60s validity.
- **Stop:** stop-limit, limit = trigger ± 1%; retry once, then marketable limit.
- **Trailing:** activates at 0.75R, trails by 0.25R (updated every minute).
- **Hard time stop:** `min(12 min, 3 × avg winning hold time)`.
- **GTT disaster stop:** 20% away, placed immediately.
- **No partial exits** (1 lot).

---

## 7. Strategy B — Mean-Reversion (Range regime only, confidence ≥ 70%)

### Entry triggers
- **Long fade:** spot ≤ ORB Low×1.002, RSI(5m)<30, price >0.3% below VWAP, bullish
  rejection wick (lower shadow ≥2× body, close>open).
- **Short fade:** opposite at ORB High.
- **Volume filter:** current 5-min volume < 1.2× average (else possible breakout).

### Option selection
ATM / slightly-OTM, `|delta| 0.3–0.5`, tight spread.

### Exit & sizing
- **Target:** return to VWAP → exit 100%.
- **Stop:** just beyond ORB boundary (0.2% buffer).
- **Time stop:** 20 min.
- **Risk cap:** `(stop distance × lotSize) ≤ ₹750`, else skip.

---

## 8. Safety Mode (Whipsaw)
No new trades. Existing positions managed normally.

---

## 9. Global Risk Controls
- **Daily loss limit:** –3% (₹3,000) → stop for day.
- **Profit lock:** +3% → move loss limit to –1%; +5% → close all, halt.
- **Portfolio heat:** ≤ ₹2,000 total.
- **Consecutive losses:** after 3, only signals with original confidence >0.65 until a win.
- **All exits via stop-limit**, never market.

---

## 10. Data — All Free, All Local
- Upstox API: real-time price, OI, Greeks, spread.
- Upstox Historical: 1/5/15-min OHLCV → `pandas-ta` for VWAP, ADX, ATR, EMA, RSI.
- India VIX from Upstox/NSE (context only — NOT used for sizing).
- ORB, Trend Persistence, Breakout Success Rate computed locally.

*No paid feeds. No external vendor dependencies. No VIX/day-of-week/time-of-day sizing
multipliers (deliberately removed — too many hand-tuned knobs to fit a small sample).*

---

## 11. Logging & Improvement
Log per trade: timestamp, symbol, regime, confidence, skip reason (if any), outcome,
MFE/MAE, hold time, **regime-before-trade**, **regime-after-exit**.

**Weekly review:** per-regime win rate, profit factor, avg R.
Use this to **validate the regime detector**, not to add filters prematurely.

---

## 12. Implementation Phases
- **Phase 1:** Health monitor; regime detector (4 regimes + confidence); Strategy A + 5 sanity
  checks; stop-limit orders; global risk controls; logging.
- **Phase 2:** Strategy B (mean-reversion) + selection scoring; trailing/hard-time stops; GTT disaster stop.
- **Phase 3:** Weekly backtest of thresholds; log feature vectors for future ML (no model training <500 trades).

---

*Ranking of source drafts: PLAN_FINAL_FINAL (best design) > PLAN_FINAL (best reference) >
PLAN_MASTER > PLAN_FOR_AHEAD2 > PLAN_FOR_AHEAD. This document supersedes all five.*
