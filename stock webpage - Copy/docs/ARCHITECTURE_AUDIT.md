# ARCHITECTURE AUDIT

## 1. Folder Map
```text
/ (Monorepo Root)
├── /app/                   # React + Vite + TypeScript Frontend
│   ├── /src/
│   │   ├── /components/    # Radix UI / shared components
│   │   ├── /features/      # Domain specific logic (e.g., options module)
│   │   ├── /hooks/         # Custom React hooks
│   │   ├── /lib/           # Utilities
│   │   ├── /pages/         # Full page views (OptionsPage, HomePage, etc.)
│   │   ├── /services/      # Frontend API connectors
│   │   └── /store/         # Global state management
├── /server/                # Node + Express Backend
│   ├── index.js            # Main server entry, OAuth, API endpoints
│   ├── mlScreener.js       # Institutional-grade ML signal screener
│   └── optionsService.js   # Option chain logic, analytics, greeks
├── /api/                   # Vercel Serverless Functions
│   ├── /options/           # Serverless option data routes
│   ├── /analytics/         # Serverless analytics routes
│   └── intraday.ts, ltp.ts # Various market data lambdas
└── /docs/                  # Documentation
```

## 2. Dependencies
- **Frontend**: `react`, `react-dom`, `vite`, `tailwindcss`, `radix-ui` (primitives), `recharts`, `lightweight-charts`, `axios`, `zod`, `react-hook-form`, `lucide-react`, `@supabase/supabase-js`.
- **Backend (Express/Serverless)**: `express`, `cors`, `axios`, `dotenv`, `csv-parser`, `node-cache`, `yahoo-finance2` (for market data and historical), `technicalindicators` (for ML screener indicators like RSI, EMA, BB, VWAP), `rss-parser` (for global news).

## 3. Data Flow
1. **Market Data (Equities & Indices)**: Upstox API -> `server/optionsService.js` / `api/ltp.ts` -> Frontend UI.
2. **Market Data (Commodities)**: Yahoo Finance (proxying MCX via USD/INR dynamic multiplier) -> Backend -> Frontend UI.
3. **Screening/Signals**: Yahoo Finance historicals + `technicalindicators` -> `server/mlScreener.js` (computes institutional scores) -> `/api/news` -> `TradingSuggestionPage`.
4. **Paper Trading/Persistence**: Frontend UI -> Supabase Postgres Database (via `supabase_trades_table.sql` schemas).

## 4. API Flow
- **Authentication**: OAuth 2.0 via Upstox (`/auth/upstox` -> Upstox Login -> `/callback` -> Session Token).
- **Options**: `/api/options/dashboard`, `/api/options/chain`, and `/api/options/chain/ltp` providing varying weights of payloads for rapid polling versus deep analytics.
- **Screener**: `/api/news` triggers intense parallel screening loops (`swing` and `intraday`), taking multiple seconds to evaluate 600+ symbols.

## 5. Bottlenecks
- **Display vs Decision Processing**: The `mlScreener.js` handles massive computational loads inside a single Node thread upon request. Display data (LTP) is fetched synchronously on the same processes handling complex logic.
- **Rate Limiting (Yahoo Finance)**: The backend uses simple jitter and caching (`ltpCache`) to avoid Yahoo Finance IP bans, which does not scale for a multi-user platform.
- **Synchronous Upstox Polling**: `/api/options/chain` triggers synchronous outgoing requests to Upstox on every client poll, heavily rate-limiting concurrent users.

## 6. Duplicate Logic
- **Vercel Serverless vs Express**: There is a split-brain architecture where `/api/` (Vercel lambdas) and `/server/index.js` (Express endpoints) duplicate routes (e.g., `ltp`, `intraday`, `options`).
- **Indicator Calculations**: Redundant mapping and calculation of `technicalindicators` occurs in multiple isolated functions inside `mlScreener.js`.

## 7. Dead Code
- Unused/Duplicate Vercel configs and test scripts (`test_features.js`, `test_quote.js`, `test_yf.js`, `test_screener.js`) left over from development.

## 8. Security Issues
- **Token Management**: `let accessToken = null;` inside `server/index.js` acts as a global singleton, meaning one user's Upstox token is shared globally across the Express server.
- **Error Handling Details**: Internal API errors and payloads (including raw Yahoo Finance/Upstox errors) are passed directly to the client responses.
- **Missing CORS restrictions**: `app.use(cors())` is completely open, allowing any domain to hit the backend.

## 9. Performance Issues
- **Sub-second Polling**: The current architecture allows clients to poll `/api/ltp` multiple times a second, hitting the backend aggressively without WebSocket multiplexing or Pub/Sub.
- **Screener Payload Size**: `mlScreener.js` returns massive JSON payloads (thousands of objects with deep technical texts) without pagination, freezing the main thread during serialization.
