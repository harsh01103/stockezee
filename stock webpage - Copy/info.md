# 📚 The Complete Stock Study Monorepo Handbook - Extended Edition

Welcome to the exhaustive, in-depth architectural and operational guide to the stock-study-monorepo. 
This document has been expanded to provide granular, line-by-line visibility into the system architecture, mathematical models, database schemas, and data flow.

---

## Table of Contents
1. Executive Summary & Vision
2. Monorepo Architecture Overview
3. Root Configuration & Tooling
4. Frontend Application (`/app`) Deep Dive
5. Backend Express API (`/server`) Deep Dive
6. ML Screener Mathematical Models (`mlScreener.js`)
7. Auto-Trading Pipeline (`autoTrader.js` & `telegramPoller.js`)
8. Document Intelligence Engine (`docintel/pipeline.js`)
9. Serverless Lambdas (`/api`)
10. Database Architecture & Complete Migrations Schema
11. Global Safety Modes & Security
12. Known Bottlenecks & Audit Notes
13. Glossary of Terms
14. System Logs & Error Codes Matrix

---

## 1. Executive Summary & Vision
The stock-study-monorepo is a cutting-edge web application crafted for holistic stock market analysis, institutional-grade screening, options analytics, and algorithmic trading. It acts as an integrated sandbox supporting both simulated (paper) trading and live execution. The platform merges high-performance fundamental data retrieval with complex technical ML scoring.

Our vision is to provide retail traders with tools typically reserved for AMCs and Hedge Funds:
- Volatility Contraction Pattern (VCP) detection.
- Deep, AI-driven fundamental analysis via the DocIntel engine.
- Zero-latency options chain visualization.

---

## 2. Monorepo Architecture Overview
This project uses a standard monorepo pattern to maintain synchronicity between frontend clients and backend services.
- **`/app/`**: React SPA (Vite).
- **`/server/`**: Node.js Express server.
- **`/api/`**: Vercel Serverless Functions.
- **`/docs/`**: Deep technical documentation.

---

## 3. Root Configuration & Tooling
### 3.1 `package.json`
```json
{
  "name": "stock-study-monorepo",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "start": "vercel dev",
    "build": "npm --prefix app install && npm --prefix app run build"
  },
  "dependencies": {
    "axios": "^1.13.5",
    "csv-parser": "^3.0.0",
    "dotenv": "^17.3.1",
    "node-cache": "^5.1.2",
    "node-fetch": "^2.7.0",
    "rss-parser": "^3.13.0",
    "technicalindicators": "^3.1.0",
    "yahoo-finance2": "^2.14.0"
  }
}
```

### 3.2 Environment Variables (`.env`)
```env
VITE_SUPABASE_URL="https://your-project.supabase.co"
VITE_SUPABASE_ANON_KEY="your_anon_key"
UPSTOX_API_KEY="your_upstox_api_key"
UPSTOX_API_SECRET="your_upstox_api_secret"
UPSTOX_REDIRECT_URI="http://localhost:4000/callback"
APP_MODE="SIMULATION"
```

---

## 4. Frontend Application (`/app`) Deep Dive

### 4.1 Page Level Routing (`/src/pages`)
1. **HomePage.tsx**: The main entry point.
2. **DashboardPage.tsx**: Displays P&L, open positions, and margin.
3. **OptionsPage.tsx**: Options chain dashboard.
4. **TradingSuggestionPage.tsx**: ML Screener visualizations.
5. **DemoTrading.tsx**: Sandboxed simulated trading environments.
6. **DemoCommoditiesTrading.tsx**: Commodities simulation.
7. **NewsPage.tsx**: DocIntel and standard news feeds.
8. **GeneralNewsPage.tsx**: Macro news.
9. **EconomicCalendarPage.tsx**: Tracks macro-economic events (CPI, Fed Rates).
10. **LearnerPage.tsx**: Educational onboarding module.
11. **LoginPage.tsx**: Upstox OAuth authentication.
12. **ReplayPage.tsx**: Visually replay historical trades tick-by-tick.

### 4.2 Feature Modules (`/src/features`)
- **`docintel/`**: UI components for Document Intelligence (confidence scores, tone, risk).
- **`options/`**: Chain rendering logic, greek tables, and payoff charts.
- **`quality/`**: Fundamental stock quality metrics UI.
- **`regime/`**: Visualizations for detecting bullish/bearish market regimes.
- **`replay/`**: Logic and UI for trade replays.
- **`shadow/`**: Shadow-mode testing interfaces for algorithmic strategies.
- **`signals/`**: Ingestion and display of Telegram/algorithmic signals.

---

## 5. Backend Express API (`/server`) Deep Dive

### 5.1 Safety Middleware Lock
```javascript
const GLOBAL_MODE = process.env.APP_MODE || 'SIMULATION';
app.use((req, res, next) => {
    const isExecutionEndpoint = (req.path.includes('/execute') || req.path.includes('/place_order') || req.path.includes('/trade')) && !req.path.includes('/api/ledger');
    
    if (isExecutionEndpoint && GLOBAL_MODE !== 'LIVE') {
        console.warn(`[SAFETY] Blocked execution attempt on ${req.path} in ${GLOBAL_MODE} mode`);
        return res.status(403).json({
            error: 'SAFETY_LOCK_ACTIVE',
            message: `Platform is running in ${GLOBAL_MODE} mode. Live execution is strictly disabled.`,
            mode: GLOBAL_MODE
        });
    }
    next();
});
```

---

## 6. ML Screener Mathematical Models (`mlScreener.js`)

### 6.1 Anchored VWAP (AVWAP)
```javascript
function computeAVWAP(quotes, fromIdx) {
    let cumVP = 0, cumV = 0;
    for (let i = fromIdx; i < quotes.length; i++) {
        const tp = (quotes[i].high + quotes[i].low + quotes[i].close) / 3;
        cumVP += tp * quotes[i].volume; cumV += quotes[i].volume;
    }
    return cumV > 0 ? cumVP / cumV : quotes[quotes.length - 1].close;
}
```

### 6.2 Supertrend
```javascript
function computeSupertrend(quotes, period = 10, mult = 3) {
    const c = quotes.map(q => q.close), h = quotes.map(q => q.high), l = quotes.map(q => q.low);
    const tr = []; 
    for (let i = 1; i < quotes.length; i++) {
        tr.push(Math.max(h[i] - l[i], Math.abs(h[i] - c[i - 1]), Math.abs(l[i] - c[i - 1])));
    }
    const atr = []; let trend = 1, ub = 0, lb = 0;
    for (let i = 0; i < tr.length; i++) {
        if (i < period - 1) { atr.push(null); continue; }
        atr.push(i === period - 1 ? tr.slice(0, period).reduce((a, b) => a + b, 0) / period : (atr[i - 1] * (period - 1) + tr[i]) / period);
    }
    for (let i = period; i < c.length; i++) {
        const a = atr[i - 1]; if (!a) continue;
        const hl2 = (h[i] + l[i]) / 2, nu = hl2 + mult * a, nl = hl2 - mult * a;
        ub = (nu < ub || c[i - 1] > ub) ? nu : ub; 
        lb = (nl > lb || c[i - 1] < lb) ? nl : lb;
        if (c[i] > ub) trend = 1; else if (c[i] < lb) trend = -1;
    }
    return { isBullish: trend === 1 };
}
```

### 6.3 Volatility Contraction Pattern (VCP)
```javascript
function detectVCP(quotes) {
    const n = quotes.length;
    if (n < 40) return { isVCP: false, contractions: 0 };
    const last40 = quotes.slice(-40);
    const high40 = Math.max(...last40.map(q => q.high));
    let contractions = 0;
    let prevDepth = Infinity;
    let inPullback = false;
    let pullbackLow = high40;

    for (let i = 0; i < last40.length; i++) {
        if (last40[i].close < high40 * 0.97 && !inPullback) {
            inPullback = true;
            pullbackLow = last40[i].low;
        } else if (inPullback) {
            pullbackLow = Math.min(pullbackLow, last40[i].low);
            if (last40[i].close > pullbackLow * 1.03) {
                inPullback = false;
                const depth = (high40 - pullbackLow) / high40;
                if (depth < prevDepth) {
                    contractions++;
                    prevDepth = depth;
                }
            }
        }
    }
    return { isVCP: contractions >= 2, contractions };
}
```

---

## 7. Auto-Trading Pipeline (`autoTrader.js` & `telegramPoller.js`)

### 7.1 AutoTrader State Machine
```javascript
// Pending signals waiting for limit order
const pendingSignals = [];

// Track active signals that are OPEN and waiting for targets
const activeSignalMeta = new Map();

// Track which contractSymbols have already been entered to prevent duplicates
const enteredContracts = new Set();
```

### 7.2 Queueing Logic
```javascript
export function queueSignal(signal) {
  if (signal.action === "SELL" && signal.hedgeStrike) {
      signal.contractSymbol = `${signal.underlying} ${signal.expiry} ${signal.strike}/${signal.hedgeStrike} ${signal.side} SPREAD`;
  }
  
  const isDuplicate = pendingSignals.some(s => s.contractSymbol === signal.contractSymbol)
    || enteredContracts.has(signal.contractSymbol)
    || getLedgerState().trades.some(t => t.status === "OPEN" && t.contractSymbol === signal.contractSymbol);
  
  if (isDuplicate) {
    console.log(`[AutoTrader] Ignoring duplicate signal for ${signal.contractSymbol}`);
    return false;
  }
  pendingSignals.push(signal);
  return true;
}
```

---

## 8. Document Intelligence Engine (`docintel/pipeline.js`)

### 8.1 Retrieval Scoring Algorithm
The Document Intelligence Engine utilizes a highly customized formula to rank the relevance of financial documents:
`Retrieval Score = Base Score * Primary Multiplier * Freshness Penalty * Quality Multiplier * Duplicate Penalty`
- **Base Score**: Based on document type (Filing = 100, Presentation = 85, News = 50).
- **Freshness**: Exponential decay based on days since publication.
- **Quality**: Subtractive penalty for short texts or low confidence ratings.

---

## 9. Serverless Lambdas (`/api`)

- **`/api/options/dashboard`**: Lightweight payload for high-level option statistics.
- **`/api/options/chain`**: Full payload for the options chain view.
- **`/api/analytics/`**: Endpoints for returning aggregated market statistics.
- **`intraday.ts`**: Fetches minute-by-minute candlestick data.
- **`ltp.ts`**: Specialized lambda for extremely fast Last Traded Price lookups.
- **`news.ts`**: Fetches real-time RSS/API news for individual tickers.

---

## 10. Database Architecture & Complete Migrations Schema

### 10.1 `04_company_documents.sql`
```sql
CREATE TABLE company_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    origin_type VARCHAR(50) NOT NULL, -- FILING, NEWS, PRESENTATION, ANNUAL_REPORT
    source_url TEXT,
    published_at TIMESTAMPTZ NOT NULL,
    content_quality INTEGER DEFAULT 0,
    retrieval_score NUMERIC(10, 4) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_company_documents_symbol ON company_documents(symbol);
CREATE INDEX idx_company_documents_score ON company_documents(retrieval_score DESC);
```

### 10.2 `06_intel_connection.sql`
```sql
CREATE TABLE company_document_features (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES company_documents(id) ON DELETE CASCADE,
    confidence NUMERIC(5, 2) DEFAULT 0,
    tone VARCHAR(20), -- BULLISH, BEARISH, NEUTRAL, CAUTIOUS
    risk VARCHAR(20), -- LOW, MODERATE, HIGH, EXTREME
    evidence TEXT,
    retrieval_score NUMERIC(10, 4) DEFAULT 0
);
CREATE UNIQUE INDEX idx_doc_features_doc_id ON company_document_features(document_id);
```

### 10.3 `trade_replay.sql`
```sql
CREATE TABLE trade_replay_ticks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trade_id UUID NOT NULL,
    tick_time TIMESTAMPTZ NOT NULL,
    price NUMERIC(15, 2) NOT NULL,
    volume BIGINT NOT NULL
);
CREATE INDEX idx_replay_trade_id ON trade_replay_ticks(trade_id, tick_time);
```

---

## 11. Global Safety Modes & Security

Given the financial nature of the platform, security and safety are paramount.
- **SAFETY_LOCK_ACTIVE**: An express middleware intercepts all `/execute` or `/place_order` routes. Unless `APP_MODE` is explicitly set to `LIVE`, the system rejects the requests to ensure paper-trading integrity. This guarantees no accidental real capital is risked during development or signal testing.
- **CORS Handling**: Currently unrestricted (`app.use(cors())`), designed for local development flexibility. This must be restricted to specific Vercel domains prior to production.
- **Token Management**: The `upstox_token.json` is held as a global singleton. While acceptable for a single-user local deployment, it creates a bottleneck and security risk if deployed in a multi-tenant cloud environment.

---

## 12. Known Bottlenecks & Audit Notes

Based on the `ARCHITECTURE_AUDIT.md`, several critical system bottlenecks exist:
- **Split-Brain Routing**: Redundancy exists between `/server/index.js` (Express endpoints) and `/api/` (Vercel lambdas) for routes like `ltp` and `options`, causing a duplicated maintenance burden.
- **Compute Blocking**: The `mlScreener.js` performs heavy synchronous mathematical processing on hundreds of stocks simultaneously. The screener payload is massive (often thousands of deep JSON objects) and occasionally causes Node main-thread blocking during JSON serialization. Offloading this to a Worker Thread or a Python microservice is recommended.
- **REST Polling vs WebSockets**: The architecture currently relies heavily on sub-second REST polling for Last Traded Price (LTP). This causes high network overhead and easily hits rate limits on Upstox and Yahoo Finance. Implementation of WebSocket multiplexing via `ws` is a pending optimization.
- **Data Persistence**: The auto-trader relies heavily on in-memory maps (`activeSignalMeta`, `pendingSignals`). While it has basic re-hydration logic from the ledger, an abrupt crash could result in missed executions. Migrating the queue state directly to Redis or Supabase is a necessary production step.

---

## 13. Glossary of Terms

- **LTP**: Last Traded Price. The most recent executed price of an asset.
- **VCP**: Volatility Contraction Pattern. A price pattern characterized by a sequence of shallower pullbacks.
- **Pocket Pivot**: A volume signature indicating hidden institutional buying within a consolidation base.
- **DocIntel**: Short for Document Intelligence. The proprietary module for scoring and retrieving text-based fundamental data.
- **Greek**: Options mathematical variables (Delta, Gamma, Theta, Vega) measuring sensitivity to market factors.
- **Shadow Mode**: An execution environment where an algorithm logs intended trades against live data without actually committing capital or affecting the main paper-trading ledger.
- **Anchored VWAP (AVWAP)**: An advanced technical indicator that ties the VWAP calculation to a specific event, like an earnings release or a major high/low, to track average price.
- **Chaikin Money Flow (CMF)**: A volume-weighted indicator used to measure the amount of money flowing into and out of a security. It's heavily relied on by our screener to confirm trends.
- **Relative Strength (RS)**: Mansfield-style metric that measures a stock's performance compared to the broader market index (like Nifty 50).
- **Stage Analysis**: A long-term trend following methodology (Stage 1 to 4) utilized by the ML screener to classify where a stock is in its lifecycle.
- **Options Chain**: A listing of all available options contracts for a given security.
- **Strike Price**: The fixed price at which the owner of an option can buy or sell the underlying security.
- **Hedging**: Making an investment to reduce the risk of adverse price movements in an asset, actively used in our spread architectures.

---

## 14. System Logs & Error Codes Matrix

### Error Codes
| Code | Source | Description | Mitigation |
|---|---|---|---|
| `SAFETY_LOCK_ACTIVE` | `/server/index.js` | Attempted to execute a live trade while APP_MODE was not LIVE. | Switch APP_MODE to LIVE if intended. |
| `UPSTOX_AUTH_FAIL` | `/server/index.js` | The Upstox access token has expired or is invalid. | Re-authenticate via the /login endpoint. |
| `YF_RATE_LIMIT` | `/server/mlScreener.js` | Yahoo Finance IP rate limit exceeded during a massive screener batch run. | Increase jitter or batch size interval. |
| `DB_MIGRATION_FAIL` | Supabase | Attempted to insert a row into `company_document_features` without a valid `document_id`. | Ensure `06_intel_connection.sql` was properly executed. |
| `WS_DISCONNECT` | `/api/ltp.ts` | Real-time websocket feed disconnected unexpectedly. | Application will automatically attempt to fallback to REST polling. |
| `TELEGRAM_TIMEOUT` | `/server/services/telegramPoller.js` | Timeout when fetching updates from Telegram servers. | Poller will automatically retry after a 5000ms delay. |
| `LEDGER_DESYNC` | `/server/services/ledgerService.js` | State mismatch between local memory ledger and Supabase Postgres. | Restart Node server to trigger a clean re-hydration from Postgres. |
| `INVALID_SIGNAL` | `/server/services/signalParser.js` | Could not parse raw text into a valid JSON trade configuration. | Ensure Telegram signals match the required syntax format. |

---

## 15. Additional Code References
### 15.1 Fibonacci Retracement Function
```javascript
function computeFib(low, high) {
    const d = high - low;
    return { 
      l382: high - d * 0.382, 
      l500: high - d * 0.5, 
      l618: high - d * 0.618, 
      ext1272: high + d * 0.272, 
      ext1618: high + d * 0.618 
    };
}
```

### 15.2 Pivot Point Calculation
```javascript
function computePivots(c) {
    const pp = (c.high + c.low + c.close) / 3;
    return { 
      pp, 
      r1: 2 * pp - c.low, 
      r2: pp + (c.high - c.low), 
      s1: 2 * pp - c.high, 
      s2: pp - (c.high - c.low) 
    };
}
```

### 15.3 CMF (Chaikin Money Flow)
```javascript
function computeCMF(quotes, period = 20) {
    const n = quotes.length; if (n < period) return 0;
    let mfv = 0, vol = 0;
    for (let i = n - period; i < n; i++) {
        const hl = quotes[i].high - quotes[i].low;
        const mfm = hl > 0 ? ((quotes[i].close - quotes[i].low) - (quotes[i].high - quotes[i].close)) / hl : 0;
        mfv += mfm * quotes[i].volume; vol += quotes[i].volume;
    }
    return vol > 0 ? mfv / vol : 0;
}
```

---
## 16. Extensive Frontend Component Mapping

### `app/src/components/ui/` Reference
- **Button.tsx**: Standardized button component with `cva` variants (default, destructive, outline, secondary, ghost, link).
- **Card.tsx**: Contains `Card`, `CardHeader`, `CardFooter`, `CardTitle`, `CardDescription`, and `CardContent` for structured data display.
- **Input.tsx**: Styled form input adhering to the unified design system.
- **Label.tsx**: Radix UI label primitive with standardized typography.
- **Table.tsx**: High-density data table components (`TableHeader`, `TableRow`, `TableHead`, `TableCell`) primarily used in the Options chain view.
- **Badge.tsx**: Status indicators (e.g., showing 'OPEN', 'CLOSED', or signal direction).
- **Dialog.tsx**: Modal overlays for confirmation actions and detail views.
- **Select.tsx**: Custom dropdown components used for ticker selection and regime filtering.
- **Tabs.tsx**: Interface segmentation used heavily in the `TradingSuggestionPage`.
- **Toast.tsx**: Non-blocking notification system for trade executions and signal alerts.

### `app/src/components/` Reference
- **Header.tsx**: The persistent navigation bar containing user avatar, balance, and routing links.
- **LogoutButton.tsx**: Clear local storage and terminate the Upstox session token.
- **StockChart.tsx**: The heavy charting component. It receives timeframe data and renders Candlesticks. It supports overlaying technical indicators (e.g., drawing the AVWAP line dynamically).
- **StockSearch.tsx**: A debounced autocomplete input field querying the `security_master` table to find valid tickers.
- **TradeHistory.tsx**: A complex tabular view iterating over the `ledger` array. It calculates row-level P&L and highlights winning vs losing trades using dynamic Tailwind classes.

---
## 17. Security Master Data Specifications

The system relies on a unified dictionary of tradable assets. This master data ensures all components (Screener, Options, AutoTrader) reference the same symbol formats.

```json
[
  {
    "symbol": "RELIANCE",
    "name": "Reliance Industries Ltd",
    "exchange": "NSE",
    "type": "EQ",
    "lot_size": 1,
    "tick_size": 0.05
  },
  {
    "symbol": "NIFTY",
    "name": "Nifty 50 Index",
    "exchange": "NSE",
    "type": "IDX",
    "lot_size": 50,
    "tick_size": 0.05
  },
  {
    "symbol": "CRUDEOIL",
    "name": "Crude Oil",
    "exchange": "MCX",
    "type": "COMM",
    "lot_size": 100,
    "tick_size": 1.00
  }
]
```
This metadata is populated by `03_security_master.sql` and heavily cached in `node-cache` inside the Express server to prevent redundant DB calls during high-frequency screening.

This completes the comprehensive overview of the stock-study-monorepo. 
Every module, schema, and API endpoint is documented for ongoing maintenance and onboarding of new developers.---
## 18. Exhaustive API Endpoints Reference

### 18.1 Express API (\/server/index.js\)
*   **\GET /auth/upstox\**
    *   **Description**: Initiates the Upstox OAuth 2.0 flow. Redirects the user to the Upstox login dialog.
    *   **Parameters**: \edirect_uri\ (optional, defaults to \http://localhost:4000/callback\).
*   **\GET /callback\**
    *   **Description**: Handles the callback from Upstox, exchanges the authorization code for an access token, and saves it to \upstox_token.json\.
*   **\GET /api/ledger\**
    *   **Description**: Returns the complete simulated ledger state (open trades, closed trades, total realized P&L).
    *   **Response**: \{ trades: [], realizedPnL: 0, balance: 1000000 }\
*   **\POST /api/execute\**
    *   **Description**: Manually executes a trade in the simulated ledger. Blocked by middleware if \APP_MODE\ is \LIVE\.
    *   **Body**: \{ symbol: "RELIANCE", action: "BUY", quantity: 1, type: "MARKET" }\
*   **\POST /api/close_position\**
    *   **Description**: Closes an open position in the simulated ledger at the current LTP.
    *   **Body**: \{ tradeId: "uuid" }\
*   **\GET /api/auto-trader/status\**
    *   **Description**: Returns the status of the automated trading pipeline (pending signals, active signals, watchdog status).
    *   **Response**: \{ pendingCount: 0, activeCount: 2, status: "RUNNING" }\
*   **\DELETE /api/auto-trader/queue\**
    *   **Description**: Clears all pending signals from the auto-trader queue.
*   **\GET /monitoring/health\**
    *   **Description**: Basic health check endpoint.
    *   **Response**: \{ status: "ok", timestamp: "..." }\

### 18.2 Vercel Serverless API (\/api/*\)
*   **\GET /api/options/dashboard\**
    *   **Description**: Returns a lightweight summary of options data for the main indices (NIFTY, BANKNIFTY).
    *   **Response**: \{ symbol: "NIFTY", underlyingLTP: 22000, atmStrike: 22000, iv: 14.5 }\
*   **\GET /api/options/chain?symbol=NIFTY&expiry=2024-05-30\**
    *   **Description**: Returns the complete options chain for a given symbol and expiry, including Greeks (Delta, Gamma, Theta, Vega) and Open Interest (OI) data.
    *   **Response**: \{ calls: [...], puts: [...], expiries: [...] }\
*   **\GET /api/ltp?symbol=RELIANCE\**
    *   **Description**: Extremely fast Last Traded Price lookup. Uses caching and Upstox API.
    *   **Response**: \{ symbol: "RELIANCE", ltp: 2950.50, change: 12.00, percentChange: 0.41 }\
*   **\GET /api/intraday?symbol=RELIANCE&interval=1m\**
    *   **Description**: Returns intraday candlestick data for the specified symbol and interval.
    *   **Response**: \{ quotes: [{ time: "...", open: 2940, high: 2955, low: 2938, close: 2950, volume: 15000 }, ...] }\
*   **\GET /api/news?symbol=RELIANCE\**
    *   **Description**: Aggregates news from various sources (RSS, DocIntel) for a specific symbol.
    *   **Response**: \{ articles: [{ title: "...", source: "...", url: "...", publishedAt: "..." }, ...] }\

---
## 19. Advanced State Management (Zustand & Context)

While the application utilizes Supabase for persistent data, local state is managed via specialized stores to optimize React rendering performance:

*   **\useLedgerStore.ts\**: Manages the optimistic UI updates for the paper-trading ledger. When a trade is executed, this store updates immediately before the Supabase mutation resolves, ensuring a snappy user experience.
*   **\useMarketDataStore.ts\**: A centralized hub for incoming LTP and quote data. This prevents multiple components from independently polling the backend for the same ticker.
*   **\useSignalStore.ts\**: Subscribes to the auto-trader status and displays real-time toast notifications when a new signal is ingested or executed.

---
## 20. Code Formatting and Linting

The repository strictly enforces code quality through:
*   **ESLint**: Configured with strict TypeScript rules (@typescript-eslint/recommended-type-checked).
*   **Prettier**: Standardized formatting (2 spaces, single quotes, no semicolons).
*   **Husky**: Pre-commit hooks run linting and type-checking to prevent broken code from being pushed to the repository.

This extensive documentation serves as the ultimate source of truth for the \stock-study-monorepo\. 
It provides developers with the necessary context, architectural understanding, and code-level details to maintain and extend the platform effectively.
---
## 21. Stock Trading Mechanics: Lifecycle of a Trade

The application provides a seamless, end-to-end lifecycle for stock trading, ranging from initial signal detection to final order execution and ledger management. This system operates identically for both Equities (NSE) and Commodities (MCX, via Yahoo proxies), abstracting the complexity of the underlying broker APIs.

### 21.1 Trade Origination & Signal Intake
A trade originates in one of three ways:
1.  **Manual Execution**: A user visually analyzes a chart on \DemoTrading.tsx\ and clicks "Buy" or "Sell". This constructs an execution payload sent to \/api/execute\.
2.  **ML Screener Trigger**: The \mlScreener.js\ flags a stock (e.g., RELIANCE breaking out of a VCP pattern) and queues it for execution if automated rules are met.
3.  **Telegram NLP Parser**: \	elegramPoller.js\ scrapes a channel, \signalParser.js\ extracts a target and stop-loss, and the payload is pushed to \utoTrader.js\.

### 21.2 The Execution Engine (\ledgerService.js\)
When a trade payload (e.g., \{ symbol: "RELIANCE", action: "BUY", quantity: 50, type: "MARKET" }\) hits the backend, the following sequence occurs:
1.  **Safety Intercept**: The global Express middleware checks \process.env.APP_MODE\. If it's set to \SIMULATION\, the physical call to the Upstox API is blocked.
2.  **Live Price Validation**: The ledger service calls \getOptionChainLtp()\ or the Upstox quote API to fetch the absolute latest Last Traded Price (LTP). Trades cannot be executed on stale prices.
3.  **Margin Check**: The simulated ledger verifies if the user's available balance (\alance\ - \usedMargin\) can cover the \quantity * LTP\.
4.  **Order Booking**: The trade is instantiated in memory as an \OPEN\ position with properties: \	radeId\, \entryPrice\, \	imestamp\, \quantity\, \ction\.
5.  **Persistence**: The state is asynchronously written to the Supabase \ledger\ table to survive server restarts.

### 21.3 Mark-To-Market (MTM) P&L Tracking
Once a position is \OPEN\, the frontend \DashboardPage.tsx\ and backend \utoTrader.js\ enter a continuous polling loop.
*   **Backend Watchdog**: \utoTrader.js\ loops through \ctiveSignalMeta\, fetching live LTPs. If the LTP crosses the predefined \	arget\ or \stopLoss\, it automatically triggers a \/close_position\ request.
*   **Frontend UI Updates**: \useLedgerStore.ts\ recalculates the unrealized P&L every 1000ms by comparing the \entryPrice\ against the incoming streaming LTPs.

### 21.4 Trade Closure
When a user manually clicks "Close" or the AutoTrader hits a stop-loss:
1.  The \	rade.status\ is flipped from \OPEN\ to \CLOSED\.
2.  The \exitPrice\ is locked in based on the live LTP.
3.  The \ealizedPnL\ is calculated: \(exitPrice - entryPrice) * quantity\ (inverted for short sells).
4.  The margin is released back to the user's available balance.

---
## 22. Charting and Market Data Pipelines

The visual representation of stock data is a critical component of the platform, requiring high-performance rendering and low-latency data feeds.

### 22.1 The Charting Engine (\StockChart.tsx\)
The platform utilizes **TradingView's Lightweight Charts**, a heavily optimized HTML5 canvas charting library.
*   **Candlestick Series**: Used to render OHLC (Open, High, Low, Close) data.
*   **Line Series Overlay**: Used dynamically to plot moving averages (EMA, SMA) and Anchored VWAP lines directly on top of the price action.
*   **Volume Histogram**: Plotted on a separate pane at the bottom of the chart to visualize buying/selling pressure.

### 22.2 Data Ingestion: Intraday Charts (\/api/intraday\)
When a user opens a chart, the following pipeline fetches the historical candles:
1.  **Request**: Frontend requests \/api/intraday?symbol=RELIANCE&interval=5m\.
2.  **Upstox / Yahoo Routing**:
    *   If it's an Indian Equity (NSE), the backend formats the request for Upstox's historical API, converting timestamps to the required format.
    *   If it's a Commodity (MCX) or US stock, the backend uses \yahoo-finance2\ (\yahooFinance.chart()\) to fetch the data.
3.  **Normalization**: The diverse responses from different brokers are flattened into a standard format: \[{ time, open, high, low, close, volume }]\.
4.  **UI Rendering**: The \StockChart.tsx\ component ingests this array and paints the canvas.

### 22.3 Data Ingestion: Real-time Streaming (LTP)
To keep the charts "alive", the system uses a combination of WebSockets (where available) and high-frequency REST polling.
*   **The \ltpCache\ Mechanism**: To avoid IP bans from Yahoo Finance and rate limits from Upstox, the Express server maintains an in-memory \
ode-cache\ for LTPs.
*   **Request Coalescing**: If 50 users are viewing the RELIANCE chart, the frontend fires 50 requests/second. The backend intercepts these, fetches the price *once* from the broker, caches it for 1000ms, and serves the cached value to all 50 users simultaneously.
*   **Data Patching**: When a new LTP arrives, the \StockChart.tsx\ component uses the \update()\ method of the \candlestickSeries\ to append a new candle or mutate the current, incomplete minute-candle in real-time.
