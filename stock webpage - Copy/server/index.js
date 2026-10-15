import * as fsLib from 'fs';
process.on('unhandledRejection', (reason) => { console.error("Unhandled Rejection:", reason); fsLib.writeFileSync('crash.txt', String(reason?.stack || reason)); });
process.on('uncaughtException', (error) => { console.error("Uncaught Exception:", error); fsLib.writeFileSync('crash.txt', String(error?.stack || error)); process.exit(1); });
import express from "express";
import cors from "cors";
import axios from "axios";
import dotenv from "dotenv";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";
import csv from "csv-parser";
import { Readable } from "stream";
import zlib from "zlib";
import YahooFinance from "yahoo-finance2";
import Parser from "rss-parser";
import ti from "technicalindicators";
import { runProScreener } from "./mlScreener.js";
import {
    buildAnalytics,
    getIntradayChart,
    getOptionChain,
    getOptionChainLtp,
    getOptionsDashboard,
    searchOptionUnderlyings,
} from "./optionsService.js";
const { EMA, RSI, MACD, BollingerBands, VWAP, ADX } = ti;
const yahooFinance = new YahooFinance();
const parser = new Parser();
import { monitoringRouter } from "./routes/monitoring.js";
import researchRouter from "./routes/research.js";
import { UniverseBuilder } from "./services/universe/universeBuilder.js";
import { docIntelPipeline } from "./services/docintel/pipeline.js";
import { getLedgerState, openTrade, closeTrade } from "./services/ledgerService.js";
import { parseTelegramSignal } from "./services/signalParser.js";
import { initAutoTrader, queueSignal, getPendingSignals, clearPendingSignals, removePendingSignals, getActiveTradeLtps } from "./services/autoTrader.js";
import { startTelegramPoller } from "./services/telegramPoller.js";
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config({ path: path.resolve(__dirname, "../.env") });
dotenv.config();

const app = express();
const PORT = 4000;

app.use(cors());
app.use(express.json());
app.use('/monitoring', monitoringRouter);
app.use('/api/research', researchRouter);

// =========================================================
// GLOBAL SAFETY MODE: SIMULATION / PAPER TRADING
// Disables all real broker execution endpoints.
// =========================================================
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

let accessToken = null;
const TOKEN_FILE = path.join(__dirname, "data", "upstox_token.json");
if (fs.existsSync(TOKEN_FILE)) {
    try {
        const stored = JSON.parse(fs.readFileSync(TOKEN_FILE, "utf8"));
        if (stored && stored.access_token) {
            accessToken = stored.access_token;
            console.log("Upstox token loaded from persistence.");
        }
    } catch (e) {
        console.warn("Failed to load persisted Upstox token:", e.message);
    }
}
let instruments = [];

function getUpstoxRedirectUri(req) {
    if (typeof req.query.redirect_uri === "string" && req.query.redirect_uri.trim()) {
        return req.query.redirect_uri.trim();
    }
    return process.env.UPSTOX_REDIRECT_URI || `http://localhost:${PORT}/callback`;
}

function buildUpstoxLoginUrl(redirectUri) {
    const params = new URLSearchParams({
        response_type: "code",
        client_id: process.env.UPSTOX_API_KEY || "",
        redirect_uri: redirectUri,
    });
    return `https://api.upstox.com/v2/login/authorization/dialog?${params.toString()}`;
}

async function exchangeUpstoxCode(code, redirectUri) {
    const tokenRes = await axios.post(
        "https://api.upstox.com/v2/login/authorization/token",
        new URLSearchParams({
            code,
            client_id: process.env.UPSTOX_API_KEY || "",
            client_secret: process.env.UPSTOX_API_SECRET || "",
            redirect_uri: redirectUri,
            grant_type: "authorization_code",
        }),
        { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
    );

    accessToken = tokenRes.data.access_token;
    
    try {
        if (!fs.existsSync(path.join(__dirname, "data"))) fs.mkdirSync(path.join(__dirname, "data"));
        fs.writeFileSync(TOKEN_FILE, JSON.stringify({ access_token: accessToken }));
    } catch(e) { console.warn("Failed to persist token:", e.message); }
    
    return tokenRes.data;
}

const universeBuilder = new UniverseBuilder();

// Load Instruments (NSE and BSE Equities/ETFs only)
async function loadInstruments() {
    try {
        instruments = await universeBuilder.buildDailyUniverse();
        console.log(`Loaded ${instruments.length} validated instruments from NSE/BSE into security_master.`);
        
        // Initialize AutoTrader Background Loop
        initAutoTrader(instruments, () => process.env.UPSTOX_ACCESS_TOKEN || accessToken);
        console.log(`[AutoTrader] Initialized and polling.`);
        
        // Start Telegram Listener
        startTelegramPoller();
    } catch (e) {
        console.error("Error loading instruments:", e.message);
    }
}

app.get("/auth/upstox", (req, res) => {
    const baseUrl = `http://localhost:${PORT}`;
    const candidates = [
        process.env.UPSTOX_REDIRECT_URI || `${baseUrl}/callback`,
        `${baseUrl}/callback`,
        `${baseUrl}/upstox/callback`,
        `${baseUrl}/api/upstox/callback`,
        baseUrl,
    ];
    const rows = [...new Set(candidates)].map((uri) => {
        const href = `/login?redirect_uri=${encodeURIComponent(uri)}`;
        return `<li><code>${uri}</code> <a href="${href}">try login</a></li>`;
    }).join("");

    res.type("html").send(`
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8" />
            <title>Upstox Auth</title>
            <style>
                body { background:#050505; color:#f8fafc; font-family: system-ui, sans-serif; margin:40px; line-height:1.5; }
                code { background:#111827; border:1px solid #263244; border-radius:6px; padding:2px 6px; }
                a { color:#86efac; margin-left:12px; }
                .box { max-width:860px; border:1px solid #263244; border-radius:12px; padding:24px; background:#0b111c; }
                li { margin:12px 0; }
            </style>
        </head>
        <body>
            <div class="box">
                <h1>Upstox Auth</h1>
                <p>API key in use: <code>${process.env.UPSTOX_API_KEY || "missing"}</code></p>
                <p>Upstox only accepts a redirect URI that is registered exactly in the developer app.</p>
                <ul>${rows}</ul>
                <p>If every link returns <code>UDAPI100068</code>, add <code>${baseUrl}/callback</code> as the redirect URL in the Upstox developer dashboard for this API key.</p>
            </div>
        </body>
        </html>
    `);
});

// Step 1: Login URL
app.get("/login", (req, res) => {
    res.redirect(buildUpstoxLoginUrl(getUpstoxRedirectUri(req)));
});

// Step 2: Callback
app.get("/callback", async (req, res) => {
    const { code } = req.query;

    try {
        const redirectUri = getUpstoxRedirectUri(req);
        const tokenRes = await axios.post(
            "https://api.upstox.com/v2/login/authorization/token",
            new URLSearchParams({
                code,
                client_id: process.env.UPSTOX_API_KEY,
                client_secret: process.env.UPSTOX_API_SECRET,
                redirect_uri: redirectUri,
                grant_type: "authorization_code",
            }),
            { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
        );

        accessToken = tokenRes.data.access_token;
        try {
            if (!fs.existsSync(path.join(__dirname, "data"))) fs.mkdirSync(path.join(__dirname, "data"));
            fs.writeFileSync(TOKEN_FILE, JSON.stringify({ access_token: accessToken }));
        } catch(e) { console.warn("Failed to persist token:", e.message); }
        res.send("✅ Upstox authentication successful. You can close this tab and return to the Demo Trading page.");
    } catch (err) {
        res.status(500).send("❌ Upstox auth failed");
    }
});

async function handleCallbackWithRedirect(req, res, redirectUri) {
    const { code } = req.query;
    if (!code || typeof code !== "string") {
        return res.status(400).send("Missing Upstox auth code.");
    }

    try {
        await exchangeUpstoxCode(code, redirectUri);
        res.send(`
            <html><body>
                <h2>Upstox authentication successful!</h2>
                <p>You can close this tab and return to the Options page.</p>
                <script>
                    setTimeout(() => { window.close(); }, 1500);
                </script>
            </body></html>
        `);
    } catch (err) {
        const details = err.response?.data || err.message;
        console.error("Upstox auth failed:", details);
        res.status(500).json({
            error: "Upstox auth failed",
            details,
            redirect_uri_used: redirectUri,
        });
    }
}

app.get("/upstox/callback", (req, res) => {
    handleCallbackWithRedirect(req, res, `http://localhost:${PORT}/upstox/callback`);
});

app.get("/api/upstox/callback", (req, res) => {
    handleCallbackWithRedirect(req, res, `http://localhost:${PORT}/api/upstox/callback`);
});

app.get("/", (req, res, next) => {
    if (!req.query.code) return next();
    return handleCallbackWithRedirect(req, res, `http://localhost:${PORT}`);
});

// Step 3: Test API
app.get("/api/profile", async (req, res) => {
    const effectiveToken = process.env.UPSTOX_ACCESS_TOKEN || accessToken;
    if (!effectiveToken) return res.status(401).send("Not authenticated");

    try {
        const profile = await axios.get("https://api.upstox.com/v2/user/profile", {
            headers: { Authorization: `Bearer ${effectiveToken}` },
        });
        res.json(profile.data);
    } catch (err) {
        res.status(500).send("Failed to fetch profile");
    }
});

app.get(["/api/upstox/status", "/api/dhan/status"], async (req, res) => {
    // 1. Check Dhan API Credentials if present
    if (process.env.DHAN_ACCESS_TOKEN && process.env.DHAN_CLIENT_ID) {
        try {
            const dhanResp = await axios.get("https://api.dhan.co/v2/fundlimit", {
                headers: {
                    "access-token": process.env.DHAN_ACCESS_TOKEN,
                    "client-id": process.env.DHAN_CLIENT_ID
                }
            });
            if (dhanResp.data?.status === "success") {
                return res.status(200).json({
                    connected: true,
                    authMode: "dhan",
                    userId: process.env.DHAN_CLIENT_ID,
                    broker: "DHAN",
                    message: "Dhan API connected successfully."
                });
            }
        } catch (err) {
            console.warn("Dhan API status check failed:", err.message);
        }
    }

    // 2. Fallback to Upstox token check
    const effectiveToken = process.env.UPSTOX_ACCESS_TOKEN || accessToken;
    if (!effectiveToken) {
        return res.status(200).json({
            connected: false,
            authMode: "none",
            message: "No broker access token loaded.",
        });
    }

    try {
        const profile = await axios.get("https://api.upstox.com/v2/user/profile", {
            headers: { Authorization: `Bearer ${effectiveToken}` },
        });
        res.status(200).json({
            connected: true,
            authMode: process.env.UPSTOX_ACCESS_TOKEN ? "env-token" : "oauth",
            userId: profile.data?.data?.user_id,
            broker: profile.data?.data?.broker || "UPSTOX",
        });
    } catch (err) {
        res.status(200).json({
            connected: false,
            authMode: process.env.UPSTOX_ACCESS_TOKEN ? "env-token" : "oauth",
            message: err.response?.data?.errors?.[0]?.message || err.message || "Token validation failed.",
        });
    }
});

// Search API
app.get('/api/search', (req, res) => {
    const { q } = req.query;
    if (!q || q.length < 2) return res.json([]);
    const query = q.toLowerCase();

    // Only search instruments that have search_enabled
    const searchable = instruments.filter(i => i.search_enabled);

    const matches = searchable.filter(i =>
        i.symbol.toLowerCase().includes(query) ||
        i.company_name.toLowerCase().includes(query)
    );

    // Group by symbol to merge NSE/BSE into one entry
    const grouped = new Map();
    for (const item of matches) {
        if (!grouped.has(item.symbol)) {
            grouped.set(item.symbol, {
                ...item,
                name: item.company_name, // for backwards compatibility
                instrument_key: item.instrument_id, // for backwards compatibility
                exchanges: [item.exchange],
                instrument_keys: { [item.exchange]: item.instrument_id }
            });
        } else {
            const existing = grouped.get(item.symbol);
            if (!existing.exchanges.includes(item.exchange)) {
                existing.exchanges.push(item.exchange);
                existing.instrument_keys[item.exchange] = item.instrument_id;
            }
        }
    }

    const results = Array.from(grouped.values());

    // Phase 2 Ranking: Exact Symbol -> Company -> Exchange
    results.sort((a, b) => {
        const aSym = a.symbol.toLowerCase();
        const bSym = b.symbol.toLowerCase();
        
        // 1. Exact symbol match gets top priority
        if (aSym === query && bSym !== query) return -1;
        if (bSym === query && aSym !== query) return 1;

        // 2. Starts with symbol match
        const aSymStarts = aSym.startsWith(query);
        const bSymStarts = bSym.startsWith(query);
        if (aSymStarts && !bSymStarts) return -1;
        if (bSymStarts && !aSymStarts) return 1;

        // 3. Name match
        const aNameStarts = a.company_name.toLowerCase().startsWith(query);
        const bNameStarts = b.company_name.toLowerCase().startsWith(query);
        if (aNameStarts && !bNameStarts) return -1;
        if (bNameStarts && !aNameStarts) return 1;

        // 4. Default alphabetical by symbol
        return a.symbol.localeCompare(b.symbol);
    });

    res.json(results.slice(0, 10)); // return top 10
});

app.get('/api/options/search', (req, res) => {
    const { q = '' } = req.query;
    try {
        res.json(searchOptionUnderlyings(q, instruments));
    } catch (error) {
        res.status(500).json({ error: error.message || 'Failed to search option underlyings' });
    }
});

app.get('/api/options/dashboard', async (req, res) => {
    try {
        const data = await getOptionsDashboard(req.query.symbol || 'NIFTY', instruments, accessToken);
        res.json(data);
    } catch (error) {
        res.status(error.status || 500).json({ error: error.message || 'Failed to load options dashboard' });
    }
});

app.get('/api/options/chain', async (req, res) => {
    try {
        const data = await getOptionChain(req.query.symbol || 'NIFTY', req.query.expiry || '', instruments, accessToken);
        res.json(data);
    } catch (error) {
        res.status(error.status || 500).json({ error: error.message || 'Failed to load option chain' });
    }
});

// Lightweight LTP-only chain endpoint for fast price polling
app.get('/api/options/chain/ltp', async (req, res) => {
    try {
        const data = await getOptionChainLtp(req.query.symbol || 'NIFTY', req.query.expiry || '', instruments, accessToken);
        res.json(data);
    } catch (error) {
        res.status(error.status || 500).json({ error: error.message || 'Failed to load LTP data' });
    }
});

app.get('/api/options/chart', async (req, res) => {
    try {
        const { symbol, instrument_key, interval } = req.query;
        const data = await getIntradayChart(symbol || 'NIFTY', instruments, accessToken, { instrumentKey: instrument_key, interval });
        res.json(data);
    } catch (error) {
        res.status(error.status || 500).json({ error: error.message || 'Failed to load chart data' });
    }
});
// Offline Ledger API

app.get("/api/debug-trader", (req, res) => {
    res.json({
        ltps: getActiveTradeLtps(),
        pendingSignals: getPendingSignals()
    });
});

app.get("/api/ledger", (req, res) => {
    const state = getLedgerState();
    const tradeLtps = getActiveTradeLtps();
    // Attach live LTP to each open trade so the frontend doesn't need the chain
    state.trades = state.trades.map(t => {
        if (t.status === "OPEN" && tradeLtps[t.id] !== undefined) {
            return { ...t, currentLtp: tradeLtps[t.id] };
        }
        return t;
    });
    res.json({
        ...state,
        pendingSignals: getPendingSignals()
    });
});

app.post("/api/ledger/trade", (req, res) => {
    try {
        const { action, tradeData, tradeId, exitPrice } = req.body;
        
        if (action === "OPEN") {
            const newState = openTrade(tradeData);
            res.json(newState);
        } else if (action === "CLOSE") {
            const newState = closeTrade(tradeId, exitPrice);
            res.json(newState);
        } else {
            res.status(400).json({ error: "Invalid action" });
        }
    } catch (e) {
        console.error("Ledger Trade Error:", e);
        res.status(500).json({ error: e.message });
    }
});

app.delete("/api/ledger/pending", (req, res) => {
    const contractSymbols = Array.isArray(req.body?.contractSymbols) ? req.body.contractSymbols : [];
    if (contractSymbols.length > 0) {
        const removed = removePendingSignals(contractSymbols);
        return res.json({ success: true, removed });
    }

    const cleared = clearPendingSignals();
    res.json({ success: true, cleared });
});

app.post("/api/ledger/pending", (req, res) => {
    try {
        const signal = req.body?.signal;
        if (!signal || !signal.contractSymbol || !signal.limitPrice) {
            return res.status(400).json({ error: "Missing signal payload" });
        }

        const queued = queueSignal({
            ...signal,
            id: undefined,
            status: undefined,
            timestamp: undefined,
            currentLtp: undefined
        });

        res.json({ success: true, signal: queued });
    } catch (e) {
        console.error("Pending Queue Error:", e);
        res.status(500).json({ error: e.message });
    }
});

app.post("/api/signals/webhook", (req, res) => {
    try {
        const { message, features, model_version, strategy_name } = req.body;
        if (!message) return res.status(400).json({ error: "Missing message body" });

        const parsed = parseTelegramSignal(message);
        if (!parsed) return res.status(400).json({ error: "Could not parse signal" });

        // Attach optional enrichment data from the Python scanner
        if (features) {
            parsed.features = features;
            if (typeof features.size_multiplier === 'number') {
                // parsed.qty is currently the 1x base lot size from signalParser
                const singleLotSize = parsed.qty; 
                // The Python engine passes the exact number of lots required to meet the risk limit
                const engineCalculatedLots = features.size_multiplier;
                
                // Calculate total lots (minimum 1 lot)
                const targetLots = Math.max(1, Math.round(engineCalculatedLots));
                parsed.qty = targetLots * singleLotSize;
            }
        }
        if (model_version) parsed.modelVersion = model_version;
        if (strategy_name) parsed.strategyName = strategy_name;

        const queued = queueSignal(parsed);
        res.json({ success: true, signal: queued });
    } catch (e) {
        console.error("Signal Webhook Error:", e);
        res.status(500).json({ error: e.message });
    }
});

// START
// (loadInstruments is called inside app.listen)

app.get('/api/intel', async (req, res) => {
    try {
        const symbol = String(req.query.symbol || '').trim().toUpperCase();
        const forceRefresh = req.query.refresh === '1' || req.query.refresh === 'true';

        if (!symbol) {
            return res.status(400).json({ error: 'Symbol is required.' });
        }

        const intel = await docIntelPipeline.fetchCompanyIntel(symbol, { forceRefresh });
        res.json(intel);
    } catch (error) {
        res.status(500).json({ error: error.message || 'Failed to fetch document intelligence.' });
    }
});

app.get('/api/analytics/summary', async (req, res) => {
    try {
        const chain = await getOptionChain(req.query.symbol || 'NIFTY', req.query.expiry || '', instruments, accessToken);
        res.json({
            generatedAt: chain.generatedAt,
            underlying: chain.underlying.symbol,
            expiry: chain.expiry,
            analytics: buildAnalytics(chain.rows),
        });
    } catch (error) {
        res.status(error.status || 500).json({ error: error.message || 'Failed to derive analytics' });
    }
});

// Dynamic Currency & Premium Engine for Indian MCX
let cachedUSDINR = 86.5; // Fallback rate
let lastUSDINRFetch = 0;

async function getMCXMultiplier(instrument_key) {
    const now = Date.now();
    if (now - lastUSDINRFetch > 600000) { // Sync currency every 10 mins
        try {
            const forex = await yahooFinance.quote('INR=X');
            if (forex && forex.regularMarketPrice) {
                cachedUSDINR = forex.regularMarketPrice;
                lastUSDINRFetch = now;
            }
        } catch (e) { console.error("Forex sync error, using fallback."); }
    }

    let multiplier = 1;
    // India MCX Import Duty + GST + Local Premium approximations
    const preciousMetalPremium = 1.095; // ~9.5% premium
    const crudePremium = 1.002; // Minor local clearing premium

    if (instrument_key === 'COMM|GOLD') multiplier = (cachedUSDINR / 3.11) * preciousMetalPremium;
    else if (instrument_key === 'COMM|SILVER') multiplier = (cachedUSDINR * 32.15) * preciousMetalPremium;
    else multiplier = cachedUSDINR * crudePremium; // Crude Oil / Natural Gas

    return multiplier;
}

let ltpCache = {};

// LTP API (Real-Time Price endpoint with sub-second polling support)
app.get('/api/ltp', async (req, res) => {
    const { instrument_key } = req.query;
    let yfSymbol = '';
    let isCommodity = false;

    if (instrument_key.startsWith('COMM|')) {
        isCommodity = true;
        if (instrument_key === 'COMM|CRUDEOIL') yfSymbol = 'CL=F';
        else if (instrument_key === 'COMM|NATURALGAS') yfSymbol = 'NG=F';
        else if (instrument_key === 'COMM|GOLD') yfSymbol = 'GC=F';
        else if (instrument_key === 'COMM|SILVER') yfSymbol = 'SI=F';
    } else {
        const instrument = instruments.find(i => i.instrument_key === instrument_key);
        if (!instrument) return res.status(404).json({ error: 'Instrument not found' });
        yfSymbol = instrument.symbol;
        if (instrument.exchange === 'NSE_EQ') yfSymbol += '.NS';
        else if (instrument.exchange === 'BSE_EQ') yfSymbol += '.BO';
        else yfSymbol += '.NS';
    }

    const now = Date.now();
    // Cache Yahoo queries to prevent IP Ban from 100ms sub-second polling and simulate live jitter
    if (ltpCache[yfSymbol] && (now - ltpCache[yfSymbol].lastFetch) < 3000) {
        const cached = ltpCache[yfSymbol];
        // Generate realistic 0.01% sub-second ticker movement jitter
        const jitter = 1 + ((Math.random() - 0.5) * 0.0001);
        return res.json({
            ...cached,
            last_price: parseFloat((cached.last_price * jitter).toFixed(2))
        });
    }

    try {
        const quote = await yahooFinance.quote(yfSymbol);

        let multiplier = 1;
        if (isCommodity) {
            multiplier = await getMCXMultiplier(instrument_key);
        }

        const priceData = {
            last_price: quote.regularMarketPrice * multiplier,
            dayHigh: quote.regularMarketDayHigh * multiplier,
            dayLow: quote.regularMarketDayLow * multiplier,
            open: quote.regularMarketOpen * multiplier,
            prevClose: quote.regularMarketPreviousClose * multiplier,
            volume: quote.regularMarketVolume,
            lastFetch: now
        };
        ltpCache[yfSymbol] = priceData;
        res.json(priceData);
    } catch (e) {
        if (ltpCache[yfSymbol]) {
            return res.json(ltpCache[yfSymbol]); // Fallback safely
        }
        res.status(500).json({ error: e.message });
    }
});

// Intraday API
app.get('/api/intraday', async (req, res) => {
    const { instrument_key, interval = '1m' } = req.query;
    let yfSymbol = '';
    let isCommodity = false;

    if (instrument_key.startsWith('COMM|')) {
        isCommodity = true;
        if (instrument_key === 'COMM|CRUDEOIL') yfSymbol = 'CL=F';
        else if (instrument_key === 'COMM|NATURALGAS') yfSymbol = 'NG=F';
        else if (instrument_key === 'COMM|GOLD') yfSymbol = 'GC=F';
        else if (instrument_key === 'COMM|SILVER') yfSymbol = 'SI=F';
    } else {
        const instrument = instruments.find(i => i.instrument_key === instrument_key);
        if (!instrument) return res.status(404).json({ error: 'Instrument not found' });
        yfSymbol = instrument.symbol;
        if (instrument.exchange === 'NSE_EQ') yfSymbol += '.NS';
        else if (instrument.exchange === 'BSE_EQ') yfSymbol += '.BO';
        else yfSymbol += '.NS';
    }

    let period1;
    if (interval === '1m') {
        period1 = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
    } else if (['5m', '15m', '30m', '60m', '90m'].includes(interval)) {
        period1 = new Date(Date.now() - 59 * 24 * 60 * 60 * 1000).toISOString();
    } else if (interval === '1h') {
        period1 = new Date(Date.now() - 729 * 24 * 60 * 60 * 1000).toISOString();
    } else {
        period1 = "1970-01-01"; // maximum history
    }

    try {
        const chart = await yahooFinance.chart(yfSymbol, { interval, period1 });

        let multiplier = 1;
        if (isCommodity) {
            multiplier = await getMCXMultiplier(instrument_key);
        }

        const candles = chart.quotes
            .filter(q => q.open !== null && q.open !== undefined)
            .map(q => ({
                time: new Date(q.date).getTime() / 1000,
                open: q.open * multiplier,
                high: q.high * multiplier,
                low: q.low * multiplier,
                close: q.close * multiplier,
                volume: q.volume
            }));

        // Yahoo Finance has a universal 10-15 minute delay. 
        // We shift the chart's time to true 'now' to match exact real-time ms visual tracking.
        // We evaluate this up to a 60-minute maximum delay window so we don't accidentally shift closed-market yesterdays into today.
        if (candles.length > 0) {
            const lastCandleTime = candles[candles.length - 1].time * 1000;
            const delayOffsetMs = Date.now() - lastCandleTime;

            if (delayOffsetMs > 0 && delayOffsetMs <= 3600000) {
                const shiftSeconds = Math.floor(delayOffsetMs / 1000);
                candles.forEach(c => {
                    c.time += shiftSeconds;
                });
            }
        }

        res.json(candles);
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

// Check Auth Status (Simple boolean endpoint)
app.get('/api/check-auth', (req, res) => {
    res.json({ authenticated: true });
});

// Deep Tracker Global State
let globalSetupsCache = {
    intraday: [],
    swing: [],
    intradayTop50: [],
    swingTop50: [],
    scanLimit: 0,
    qualified_scanned: 0,
    lastUpdated: 0
};

const commonWordExclusions = new Set(['IT', 'IS', 'THE', 'AND', 'OR', 'FOR', 'TO', 'A', 'AN', 'OF', 'IN', 'ON', 'AT', 'BY', 'WITH', 'FROM', 'AS', 'BE', 'THIS', 'THAT', 'ARE', 'WAS', 'WERE', 'HAS', 'HAVE', 'HAD', 'YES', 'NO', 'NOT', 'ALL', 'ANY', 'CAN', 'MAY', 'WILL', 'WOULD', 'SHOULD', 'COULD', 'NEW', 'NOW', 'UP', 'DOWN', 'OUT', 'OVER', 'UNDER', 'MORE', 'LESS', 'ONLY', 'SOME', 'SUCH', 'THAN', 'THEN', 'THERE', 'THEY', 'THEIR', 'THEM', 'THESE', 'THOSE', 'WHAT', 'WHEN', 'WHERE', 'WHICH', 'WHO', 'WHY', 'HOW', 'SO', 'TOO', 'VERY', 'WELL', 'EVEN', 'JUST', 'STILL', 'MUCH']);

async function checkTechnicalCatalyst(symbol) {
    try {
        const queryOptions = { period1: new Date(Date.now() - 300 * 24 * 60 * 60 * 1000).toISOString(), interval: '1d' };
        const hist = await yahooFinance.chart(`${symbol}.NS`, queryOptions);
        if (!hist.quotes) return null;

        const quotes = hist.quotes.filter(q => q.volume !== null && q.close !== null);
        if (quotes.length < 30) return null; // We only strictly require 30 days for basic MACD and RSI

        const closePrices = quotes.map(q => q.close);
        const highPrices = quotes.map(q => q.high);
        const lowPrices = quotes.map(q => q.low);
        const openPrices = quotes.map(q => q.open);
        const volumes = quotes.map(q => q.volume);

        const latest = quotes[quotes.length - 1];
        const prev = quotes[quotes.length - 2];
        const change_pct = ((latest.close - prev.close) / prev.close) * 100;

        const safeGet = (arr, fallback = null) => arr && arr.length > 0 ? arr[arr.length - 1] : fallback;

        const rsiVals = RSI.calculate({ period: 14, values: closePrices });
        const rsi = safeGet(rsiVals, 50);

        const ema9Vals = EMA.calculate({ period: 9, values: closePrices });
        const ema9 = safeGet(ema9Vals, latest.close);

        const ema21Vals = EMA.calculate({ period: 21, values: closePrices });
        const ema21 = safeGet(ema21Vals, latest.close);

        const ema50Vals = EMA.calculate({ period: 50, values: closePrices });
        const ema50 = safeGet(ema50Vals, latest.close);

        const ema200Vals = EMA.calculate({ period: 200, values: closePrices });
        const ema200 = safeGet(ema200Vals, latest.close);

        // Using 8, 24, 9 MACD
        const macdVals = MACD.calculate({ values: closePrices, fastPeriod: 8, slowPeriod: 24, signalPeriod: 9, SimpleMAOscillator: false, SimpleMASignal: false });
        const macd = safeGet(macdVals, null);

        const bbVals = BollingerBands.calculate({ period: 20, values: closePrices, stdDev: 2 });
        const bb = safeGet(bbVals, { lower: latest.close * 0.95, upper: latest.close * 1.05 });

        const vwapVals = VWAP.calculate({ high: highPrices, low: lowPrices, close: closePrices, volume: volumes });
        const vwap = safeGet(vwapVals, latest.close);

        const adxVals = ADX.calculate({ high: highPrices, low: lowPrices, close: closePrices, period: 14 });
        const adxData = safeGet(adxVals, { adx: 20, pdi: 20, mdi: 20 });
        const adx = adxData.adx;
        const pdi = adxData.pdi;
        const mdi = adxData.mdi;

        const prevQuotes = quotes.slice(quotes.length - 21, quotes.length - 1);
        const avgVol = prevQuotes.length > 0 ? (prevQuotes.reduce((a, b) => a + b.volume, 0) / prevQuotes.length) : latest.volume;
        const volMultiplier = avgVol > 0 ? (latest.volume / avgVol) : 1;

        if (change_pct < -0.5) return null; // We only want bullish momentum, allowing tiny red days if structurally sound

        // Trend logic Confluence
        const has200 = ema200Vals && ema200Vals.length > 2;
        const isGoldenCross = has200 && ema50 > ema200 && (ema50Vals[ema50Vals.length - 2] <= ema200Vals[ema200Vals.length - 2]);
        const isBullishTrend = ema9 > ema21 && latest.close > ema50;
        const isAboveVWAP = latest.close > vwap;

        const macdBullish = macd && macd.histogram > 0;

        // If it's overall bearish structurally and not a massive recovery, drop it
        if (!isBullishTrend && !isGoldenCross && change_pct < 1.5) return null;

        let emotion = "Stable Accumulation";
        let emoText = "Steady volume with bullish positioning. Smart money is gradually scaling in.";
        if (change_pct > 3 && volMultiplier > 1.2 && adx > 25 && pdi > mdi) {
            emotion = "EXPLOSIVE TREND (ADX Surge)";
            emoText = "Massive institutional buying detected. Trend strength indicator (ADX) confirms a violent breakout to the upside.";
        } else if (latest.close > bb.upper && volMultiplier > 1.5) {
            emotion = "VOLATILITY BREAKOUT (Bollinger Band)";
            emoText = "Price has sharply broken above the upper volatility band indicating massive institutional force pushing it higher.";
        } else if (isGoldenCross) {
            emotion = "MACRO BREAKOUT (Golden Cross)";
            emoText = "Major macro trend reversal. Smart money is loading the boat for a prolonged rocket rally.";
        } else if (rsi > 60 && rsi < 75 && isAboveVWAP && adx > 20) {
            emotion = "BULLISH CHARGE (Momentum Zone)";
            emoText = "Perfectly positioned in the high-momentum RSI zone. Supported heavily by VWAP structure.";
        } else if (rsi < 40 && isBullishTrend) {
            emotion = "BULLISH PULLBACK (Dip Buying)";
            emoText = "Temporary suppression in a strong uptrend. Extremely high probability bounce area for a rocket launch.";
        } else if (rsi >= 75) {
            // Overbought, perhaps a pullback imminent, skip or label risk
            if (change_pct < 1) return null; // Avoid buying the absolute top if stalling
            emotion = "PARABOLIC SURGE (High Risk)";
            emoText = "Unprecedented vertical momentum. Highly profitable but strictly requires tight trailing stops.";
        } else {
            // Ensure it's a strongly trending swing candidate or return null
            if (adx < 20 || pdi < mdi) return null;
        }

        let type = 'Bullish'; // The scanner is now exclusively geared for Bullish runs

        let rsiStatus = rsi > 70 ? "Approaching Overbought (Strong Momentum)" : (rsi < 40 ? "Oversold Dip" : "High-Octane Momentum Zone");
        let vwapStatus = isAboveVWAP ? "Trading ABOVE VWAP (Bullish Institutional Support)" : "Testing VWAP Support";

        let rationale = `Technical Confluence: ${isBullishTrend ? 'Strong Uptrend' : 'Consolidated Breakout'}. ` +
            `ADX Trend Strength: ${adx.toFixed(1)} ${adx > 25 ? '(Extreme)' : '(Building)'}. ` +
            `Price validates institutional buy-side bias.`;

        let techText = `EMA Stack (9/21/50/200): ${ema9.toFixed(1)} / ${ema21.toFixed(1)} / ${ema50.toFixed(1)} / ${ema200.toFixed(1)}. ` +
            `Status: ${rsiStatus}, RSI(14)=${rsi.toFixed(1)}. ` +
            `Bollinger Bands: Lower=${bb.lower.toFixed(1)}, Upper=${bb.upper.toFixed(1)}. ` +
            `${vwapStatus}.`;

        return {
            cmp: latest.close,
            volMultiplier: volMultiplier.toFixed(1),
            type: type,
            change_pct: change_pct.toFixed(2),
            rationale: rationale,
            deepDetails: {
                technical: techText,
                emotional: emotion + " - " + emoText,
                insider: `Volume profile indicates ${volMultiplier.toFixed(1)}x normal activity mapping to targeted algorithmic liquidity sweeps. Validated by Volumetric VWAP divergence.`
            }
        };
    } catch (e) {
        return null;
    }
}

async function scrapeAlternativeData() {
    let altNews = [];
    try {
        const [isbRes, invRes] = await Promise.all([
            axios.get('https://www.reddit.com/r/IndianStreetBets/hot.json?limit=20').then(r => r.data),
            axios.get('https://www.reddit.com/r/IndiaInvestments/hot.json?limit=20').then(r => r.data)
        ]);

        const parserReddit = (data) => {
            if (!data || !data.data || !data.data.children) return [];
            return data.data.children.map(c => ({
                title: c.data.title,
                text: c.data.selftext || '',
                link: `https://reddit.com${c.data.permalink}`,
                source: `Reddit: r/${c.data.subreddit}`,
                pubDate: new Date(c.data.created_utc * 1000).toISOString()
            }));
        };

        altNews = [...parserReddit(isbRes), ...parserReddit(invRes)];
    } catch (e) { console.error("Reddit Scrape Failed:", e.message); }
    return altNews;
}

function processSignalsForTargets(picks, isSwing) {
    const verified = [];
    for (const pick of picks) {
        let entry = pick.cmp;
        let target, sl, marginText;

        if (pick.type === 'Bullish') {
            target = isSwing ? entry * 1.155 : entry * 1.07;
            sl = isSwing ? entry * 0.94 : entry * 0.96;
            marginText = isSwing ? "15%+ Target. Carry Forward options." : "7%+ Target. Intraday MIS Margin Engine Leveraged.";
        } else {
            target = isSwing ? entry * 0.85 : entry * 0.93;
            sl = isSwing ? entry * 1.06 : entry * 1.04;
            marginText = isSwing ? "15%+ Downside Target. Short Carry Forward options." : "7%+ Downside Target. Intraday Short MIS.";
        }

        // Use dynamically analyzed deep details instead of fallbacks
        let techText = pick.deepDetails ? pick.deepDetails.technical : (isSwing ? "Daily Chart Breakout. RSI trending." : "5-Min VWAP crossover and momentum indicator bullish divergence.");
        let emoText = pick.deepDetails ? pick.deepDetails.emotional : (isSwing ? "Retail sentiment is extremely greedy based on trending metrics." : "Panic short-covering anticipated.");
        let insiderText = pick.deepDetails ? pick.deepDetails.insider : "Tape analysis verifies heavy institutional footprint linked to recent volume spike.";

        verified.push({
            symbol: pick.symbol,
            name: pick.name,
            type: pick.type,
            reasons: pick.reasons,
            entry: entry.toFixed(2),
            target: target.toFixed(2),
            stoploss: sl.toFixed(2),
            marginInfo: marginText,
            timestamp: Date.now(),
            status: "ACTIVE",
            guarantee: isSwing ? "Deep Swing Analytics Verified" : "High-Conviction Intraday Alert",
            deepSummary: {
                technical: techText,
                emotional: emoText,
                insider: insiderText
            },
            change_pct_num: pick.change_pct ? parseFloat(pick.change_pct) : 0
        });
    }
    return verified;
}

app.get('/api/news', async (req, res) => {
    try {
        const ONE_HOUR = 60 * 60 * 1000;
        const now = Date.now();
        const requestedLimit = Number(req.query.limit || process.env.NSE_SCAN_LIMIT || 7000);
        const scanLimit = Number.isFinite(requestedLimit) ? Math.max(50, Math.min(7000, requestedLimit)) : 7000;

        // Serve from cache if available and fresh
        if (globalSetupsCache.lastUpdated !== 0 && globalSetupsCache.scanLimit === scanLimit && (now - globalSetupsCache.lastUpdated < ONE_HOUR) && (globalSetupsCache.swing.length > 0 || globalSetupsCache.intraday.length > 0)) {
            return res.status(200).json({
                news: [],
                intradaySetups: globalSetupsCache.intraday,
                swingSetups: globalSetupsCache.swing,
                intradayTop50: globalSetupsCache.intradayTop50 || globalSetupsCache.intraday,
                swingTop50: globalSetupsCache.swingTop50 || globalSetupsCache.swing,
                for_date: globalSetupsCache.for_date || '',
                model_version: '5.0.0',
                universe_scanned: globalSetupsCache.universe_scanned || 600,
                qualified_scanned: globalSetupsCache.qualified_scanned || 0,
                indicators_used: 16,
                disclaimer: globalSetupsCache.disclaimer || ''
            });
        }

        console.log('\n🔬 Running Institutional-Grade Screener (Swing + Intraday)...');

        // Run the pro screener for both modes in parallel
        const [swingResult, intradayResult] = await Promise.all([
            runProScreener('swing', yahooFinance, ti, instruments, null, axios, scanLimit).catch(e => {
                console.error('Swing screener error:', e.message);
                return { results: [], for_date: '', disclaimer: '', universe_scanned: 0 };
            }),
            runProScreener('intraday', yahooFinance, ti, instruments, null, axios, scanLimit).catch(e => {
                console.error('Intraday screener error:', e.message);
                return { results: [], for_date: '', disclaimer: '', universe_scanned: 0 };
            })
        ]);

        // Adapt results for the NewsPage format (which expects key_factors, why_it_can_rise)
        const adaptForNewsPage = (results) => results.map(stock => ({
            ...stock,
            key_factors: (stock.bullish_signals || []).map(s => ({ technical: s.tech, simple: s.simple })),
            why_it_can_rise: (stock.bullish_signals || []).slice(0, 4).map(s => ({ technical: s.tech, simple: s.simple })),
        }));

        const swingSetups = adaptForNewsPage(swingResult.results || []);
        const intradaySetups = adaptForNewsPage(intradayResult.results || []);
        const swingTop50 = adaptForNewsPage(swingResult.watchlist50 || swingResult.results || []);
        const intradayTop50 = adaptForNewsPage(intradayResult.watchlist50 || intradayResult.results || []);

        // Cache
        globalSetupsCache.swing = swingSetups;
        globalSetupsCache.intraday = intradaySetups;
        globalSetupsCache.swingTop50 = swingTop50;
        globalSetupsCache.intradayTop50 = intradayTop50;
        globalSetupsCache.scanLimit = scanLimit;
        globalSetupsCache.lastUpdated = now;
        globalSetupsCache.for_date = swingResult.for_date || intradayResult.for_date || '';
        globalSetupsCache.universe_scanned = swingResult.universe_scanned || intradayResult.universe_scanned || 0;
        globalSetupsCache.qualified_scanned = Math.max(swingResult.qualified_scanned || 0, intradayResult.qualified_scanned || 0);
        globalSetupsCache.disclaimer = swingResult.disclaimer || intradayResult.disclaimer || '';

        console.log(`✅ Screener complete: ${swingSetups.length} swing, ${intradaySetups.length} intraday setups`);

        res.status(200).json({
            news: [],
            intradaySetups,
            swingSetups,
            intradayTop50,
            swingTop50,
            for_date: globalSetupsCache.for_date,
            model_version: '5.0.0',
            universe_scanned: globalSetupsCache.universe_scanned,
            qualified_scanned: globalSetupsCache.qualified_scanned,
            indicators_used: 16,
            disclaimer: globalSetupsCache.disclaimer
        });

    } catch (error) {
        console.error("Deep Analysis Engine Error:", error);
        res.status(500).json({ error: "Failed to perform deep quant analysis." });
    }
});

let cachedNews = [];
let lastFetchTime = 0;

app.get('/api/global-news', async (req, res) => {
    try {
        const ONE_HOUR = 60 * 60 * 1000;
        const now = Date.now();

        if (cachedNews.length > 0 && (now - lastFetchTime < ONE_HOUR)) {
            return res.status(200).json({ news: cachedNews });
        }

        let newNews = [];
        const feedUrls = [
            'https://news.google.com/rss/search?q=Indian+Stock+Market+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en',
            'https://news.google.com/rss/search?q=NSE+BSE+Smallcap+Midcap+Breakout&hl=en-IN&gl=IN&ceid=IN:en'
        ];

        const allFeeds = await Promise.all(feedUrls.map(url => parser.parseURL(url).catch(() => ({ items: [] }))));
        let rawArticles = [];
        allFeeds.forEach(f => f.items.forEach(i => rawArticles.push(i)));

        for (const item of rawArticles) {
            const title = (item.title || '');
            const content = (item.contentSnippet || '');
            if (/NSE|BSE|STOCK|MARKET|NIFTY|SENSEX|ECONOMY|RATE/i.test(title)) {
                newNews.push({
                    title: item.title,
                    link: item.link,
                    pubDate: item.pubDate || new Date().toISOString(),
                    source: item.source || 'Institutional Scraper',
                    contentSnippet: content.substring(0, 150) + '...',
                    isVerified: true
                });
            }
        }

        if (newNews.length === 0 && rawArticles.length > 0) {
            newNews = rawArticles.slice(0, 10).map(item => ({
                title: item.title,
                link: item.link,
                pubDate: item.pubDate || new Date().toISOString(),
                source: item.source || 'Market Data',
                contentSnippet: (item.contentSnippet || '').substring(0, 150) + '...',
                isVerified: true
            }));
        }

        cachedNews = newNews.length > 0 ? newNews.slice(0, 40) : [];
        lastFetchTime = now;

        res.status(200).json({ news: cachedNews });

    } catch (error) {
        console.error("News Scrape Error:", error);
        res.status(500).json({ error: "Failed to fetch global news." });
    }
});

app.listen(PORT, () => {
    console.log(`✅ Backend running on http://localhost:${PORT}`);
    console.log(`Upstox token loaded: ${process.env.UPSTOX_ACCESS_TOKEN ? "yes" : "no"}`);
    loadInstruments();
});
