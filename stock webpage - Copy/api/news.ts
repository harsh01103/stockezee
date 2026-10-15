// @ts-nocheck

import { VercelRequest, VercelResponse } from "@vercel/node";
// @ts-ignore
import ti from "technicalindicators";

// Vercel Serverless maximum execution limit
export const maxDuration = 60;

let cache: any = null;
let cacheTime = 0;
let cacheLimit = 0;
const CACHE_TTL = 3600000; // 1 hour

export default async function handler(req: VercelRequest, res: VercelResponse) {
    try {
        const now = Date.now();
        const requestedLimit = Number((req.query as any)?.limit || process.env.NSE_SCAN_LIMIT || 200);
        const scanLimit = Number.isFinite(requestedLimit) ? Math.max(50, Math.min(7000, requestedLimit)) : 200;
        if (cache && cacheLimit === scanLimit && (now - cacheTime < CACHE_TTL)) {
            return res.status(200).json(cache);
        }

        console.log('\n🔬 [VERCEL] Running Institutional-Grade Screener...');

        // Dynamically import YahooFinance to avoid ERR_REQUIRE_ESM crashes on Vercel Node Runtime
        const yfModule = await import("yahoo-finance2");
        const YahooFinanceCls = (yfModule as any).default || yfModule;
        const axiosModule = await import("axios");
        const axios = (axiosModule as any).default || axiosModule;

        let yahooFinance: any;
        try {
            yahooFinance = new YahooFinanceCls();
        } catch {
            yahooFinance = YahooFinanceCls;
        }

        const instruments: any[] = []; // Used if we don't have CSV on Vercel

        // Axios is used for official NSE universe, active movers, and optional NSE quote/trade-info enrichment.
        const [swingResult, intradayResult] = await Promise.all([
            runProScreener('swing', yahooFinance, ti, instruments, null, axios, scanLimit).catch((e: any) => {
                console.error('Swing screener error:', e.message);
                return { results: [], for_date: '', disclaimer: '', universe_scanned: 0 };
            }),
            runProScreener('intraday', yahooFinance, ti, instruments, null, axios, scanLimit).catch((e: any) => {
                console.error('Intraday screener error:', e.message);
                return { results: [], for_date: '', disclaimer: '', universe_scanned: 0 };
            })
        ]);

        const responsePayload = {
            news: [],
            intradaySetups: intradayResult.results || [],
            swingSetups: swingResult.results || [],
            intradayTop50: intradayResult.watchlist50 || intradayResult.results || [],
            swingTop50: swingResult.watchlist50 || swingResult.results || [],
            for_date: swingResult.for_date || intradayResult.for_date || '',
            model_version: '5.0.0',
            universe_scanned: Math.max(swingResult.universe_scanned || 0, intradayResult.universe_scanned || 0),
            qualified_scanned: Math.max(swingResult.qualified_scanned || 0, intradayResult.qualified_scanned || 0),
            indicators_used: 16,
            disclaimer: swingResult.disclaimer || intradayResult.disclaimer || 'Educational analysis only.'
        };

        if (responsePayload.swingSetups.length > 0 || responsePayload.intradaySetups.length > 0) {
            cache = responsePayload;
            cacheTime = now;
            cacheLimit = scanLimit;
        }

        return res.status(200).json(responsePayload);
    } catch (error: any) {
        console.error("ML Screener Error on Vercel:", error?.message, error?.stack);
        if (cache) return res.status(200).json(cache);
        return res.status(500).json({
            error: "Screening engine temporarily unavailable.",
            message: error?.message,
            intradaySetups: [],
            swingSetups: [],
            model_version: '5.0.0',
            universe_scanned: 0,
            indicators_used: 0,
            disclaimer: ''
        });
    }
}


// =====================================================================
// INSTITUTIONAL SCREENER v5.0 — AMC/Fintech Grade
// Scans FULL NSE universe (small, micro, mid, large)
// Uses REAL institutional signals: Delivery-style Analysis, VCP,
// Pocket Pivots, Relative Strength Ranking, Force Index,
// Tight Closing Range, Accumulation Intensity, AVWAP, Stage Analysis
// =====================================================================

// AVWAP 
function computeAVWAP(quotes, fromIdx) {
    let cumVP = 0, cumV = 0;
    for (let i = fromIdx; i < quotes.length; i++) {
        const tp = (quotes[i].high + quotes[i].low + quotes[i].close) / 3;
        cumVP += tp * quotes[i].volume; cumV += quotes[i].volume;
    }
    return cumV > 0 ? cumVP / cumV : quotes[quotes.length - 1].close;
}

function findSwingLowIdx(quotes, lookback = 30) {
    let idx = Math.max(0, quotes.length - lookback), mn = Infinity;
    for (let i = idx; i < quotes.length; i++) { if (quotes[i].low < mn) { mn = quotes[i].low; idx = i; } }
    return idx;
}

// Supertrend 
function computeSupertrend(quotes, period = 10, mult = 3) {
    const c = quotes.map(q => q.close), h = quotes.map(q => q.high), l = quotes.map(q => q.low);
    const tr = []; for (let i = 1; i < quotes.length; i++) tr.push(Math.max(h[i] - l[i], Math.abs(h[i] - c[i - 1]), Math.abs(l[i] - c[i - 1])));
    const atr = []; let trend = 1, ub = 0, lb = 0;
    for (let i = 0; i < tr.length; i++) {
        if (i < period - 1) { atr.push(null); continue; }
        atr.push(i === period - 1 ? tr.slice(0, period).reduce((a, b) => a + b, 0) / period : (atr[i - 1] * (period - 1) + tr[i]) / period);
    }
    for (let i = period; i < c.length; i++) {
        const a = atr[i - 1]; if (!a) continue;
        const hl2 = (h[i] + l[i]) / 2, nu = hl2 + mult * a, nl = hl2 - mult * a;
        ub = (nu < ub || c[i - 1] > ub) ? nu : ub; lb = (nl > lb || c[i - 1] < lb) ? nl : lb;
        if (c[i] > ub) trend = 1; else if (c[i] < lb) trend = -1;
    }
    return { isBullish: trend === 1 };
}

// CMF 
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

// Pivot Points 
function computePivots(c) {
    const pp = (c.high + c.low + c.close) / 3;
    return { pp, r1: 2 * pp - c.low, r2: pp + (c.high - c.low), s1: 2 * pp - c.high, s2: pp - (c.high - c.low) };
}

// Fibonacci 
function computeFib(low, high) {
    const d = high - low;
    return { l382: high - d * 0.382, l500: high - d * 0.5, l618: high - d * 0.618, ext1272: high + d * 0.272, ext1618: high + d * 0.618 };
}

// ===================================================================
// INSTITUTIONAL SIGNAL #1: RELATIVE STRENGTH RANKING
// Mansfield-style: stock's % change vs Nifty % change over N days
// RS > 1 means outperforming market. AMCs rank ALL stocks by RS.
// ===================================================================
function computeRelativeStrength(quotes, niftyReturn, days) {
    const n = quotes.length;
    if (n < days + 1) return 0;
    const stockReturn = (quotes[n - 1].close - quotes[n - 1 - days].close) / quotes[n - 1 - days].close;
    return niftyReturn !== 0 ? stockReturn / Math.abs(niftyReturn) : (stockReturn > 0 ? 2 : 0);
}

// ===================================================================
// INSTITUTIONAL SIGNAL #2: VCP (Volatility Contraction Pattern)
// Mark Minervini's signature setup. Each pullback is shallower than
// the previous one — sign of supply drying up before a breakout.
// ===================================================================
function detectVCP(quotes) {
    const n = quotes.length;
    if (n < 40) return { isVCP: false, contractions: 0 };

    const last40 = quotes.slice(-40);
    const high40 = Math.max(...last40.map(q => q.high));

    // Find pullback depths from the high
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
            if (last40[i].close > high40 * 0.97) {
                const depth = (high40 - pullbackLow) / high40;
                if (depth < prevDepth) contractions++;
                prevDepth = depth;
                inPullback = false;
            }
        }
    }

    // Current price should be near the high (within 5%)
    const nearHigh = quotes[n - 1].close > high40 * 0.95;
    return { isVCP: contractions >= 2 && nearHigh, contractions };
}

// ===================================================================
// INSTITUTIONAL SIGNAL #3: POCKET PIVOT
// Gil Morales/Chris Kacher: Up-day volume > max down-day volume
// of last 10 days. Signals stealth institutional buying.
// ===================================================================
function detectPocketPivot(quotes) {
    const n = quotes.length;
    if (n < 12) return false;

    const today = quotes[n - 1];
    if (today.close <= today.open) return false; // must be up day

    // Get max volume on down days in last 10 sessions
    let maxDownVol = 0;
    for (let i = n - 11; i < n - 1; i++) {
        if (quotes[i].close < quotes[i].open) {
            maxDownVol = Math.max(maxDownVol, quotes[i].volume);
        }
    }

    return today.volume > maxDownVol && maxDownVol > 0;
}

// ===================================================================
// INSTITUTIONAL SIGNAL #4: TIGHT CLOSING RANGE (TCR)
// Professional concept: close in top 25% of day's range for
// 3+ consecutive days = controlled accumulation by institutions.
// ===================================================================
function detectTightClose(quotes, days = 5) {
    const n = quotes.length;
    if (n < days) return { isTight: false, streak: 0 };

    let streak = 0;
    for (let i = n - days; i < n; i++) {
        const range = quotes[i].high - quotes[i].low;
        if (range === 0) continue;
        const closePos = (quotes[i].close - quotes[i].low) / range;
        if (closePos >= 0.70) streak++;
        else streak = 0;
    }
    return { isTight: streak >= 3, streak };
}

// ===================================================================
// INSTITUTIONAL SIGNAL #5: ACCUMULATION INTENSITY
// Volume-weighted close position. When big players buy, they push
// close towards high with heavy volume. Industry uses this to
// detect stealth accumulation.
// ===================================================================
function computeAccumulationIntensity(quotes, period = 10) {
    const n = quotes.length;
    if (n < period) return 0;

    let score = 0;
    for (let i = n - period; i < n; i++) {
        const range = quotes[i].high - quotes[i].low;
        if (range === 0) continue;
        const closePos = ((quotes[i].close - quotes[i].low) / range) * 2 - 1; // -1 to +1
        const volWeight = quotes[i].volume / (quotes.slice(n - 20, n).reduce((a, q) => a + q.volume, 0) / 20);
        score += closePos * volWeight;
    }
    return score / period; // positive = accumulation, negative = distribution
}

// ===================================================================
// INSTITUTIONAL SIGNAL #6: FORCE INDEX (Alexander Elder)
// Combines price change × volume. Positive = buying force.
// Smoothed over 13 days for swing, 2 days for intraday.
// ===================================================================
function computeForceIndex(quotes, period = 13) {
    const n = quotes.length;
    if (n < period + 2) return 0;

    const raw = [];
    for (let i = 1; i < n; i++) {
        raw.push((quotes[i].close - quotes[i - 1].close) * quotes[i].volume);
    }

    // EMA of raw force index
    const k = 2 / (period + 1);
    let ema = raw[0];
    for (let i = 1; i < raw.length; i++) ema = raw[i] * k + ema * (1 - k);
    return ema;
}

// ===================================================================
// INSTITUTIONAL SIGNAL #7: STAN WEINSTEIN STAGE ANALYSIS
// Stage 1 = basing, Stage 2 = advancing (BUY), Stage 3 = topping,
// Stage 4 = declining. Uses 150-day MA as reference.
// ===================================================================
function detectStage(quotes, ti) {
    const n = quotes.length;
    const closePrices = quotes.map(q => q.close);
    const period = Math.min(150, n - 1);
    const smaVals = ti.SMA.calculate({ period, values: closePrices });
    if (smaVals.length < 3) return { stage: 0, smaRising: false };

    const sma = smaVals[smaVals.length - 1];
    const smaPrev = smaVals[smaVals.length - 3]; // compare to 3 days ago
    const smaRising = sma > smaPrev;
    const priceAbove = quotes[n - 1].close > sma;

    if (priceAbove && smaRising) return { stage: 2, smaRising: true }; // ADVANCING 
    if (priceAbove && !smaRising) return { stage: 3, smaRising: false }; // TOPPING
    if (!priceAbove && !smaRising) return { stage: 4, smaRising: false }; // DECLINING
    return { stage: 1, smaRising: false }; // BASING
}

// ===================================================================
// INSTITUTIONAL SIGNAL #8: NARROW RANGE (NR4/NR7)
// ===================================================================
function detectNarrowRange(quotes) {
    const n = quotes.length;
    if (n < 8) return { isNR4: false, isNR7: false };
    const todayRange = quotes[n - 1].high - quotes[n - 1].low;
    let s4 = 0, s7 = 0;
    for (let i = n - 2; i >= Math.max(0, n - 5); i--) if (todayRange < (quotes[i].high - quotes[i].low)) s4++;
    for (let i = n - 2; i >= Math.max(0, n - 8); i--) if (todayRange < (quotes[i].high - quotes[i].low)) s7++;
    return { isNR4: s4 >= 3, isNR7: s7 >= 6 };
}

// ===================================================================
// INSTITUTIONAL SIGNAL #9: BOLLINGER SQUEEZE
// ===================================================================
function detectBBSqueeze(ti, closePrices) {
    try {
        const bbVals = ti.BollingerBands.calculate({ period: 20, values: closePrices, stdDev: 2 });
        if (bbVals.length < 10) return { isSqueeze: false, width: 0, position: 0.5 };
        const recent = bbVals[bbVals.length - 1];
        const width = (recent.upper - recent.lower) / recent.middle;
        const widths = bbVals.slice(-20).map(b => (b.upper - b.lower) / b.middle);
        const sorted = [...widths].sort((a, b) => a - b);
        const pctile = sorted.indexOf(width) / sorted.length;
        const position = recent.upper !== recent.lower ? (closePrices[closePrices.length - 1] - recent.lower) / (recent.upper - recent.lower) : 0.5;
        return { isSqueeze: pctile < 0.3, width, position };
    } catch { return { isSqueeze: false, width: 0, position: 0.5 }; }
}

// Close Strength 
function closeStrength(c) { const r = c.high - c.low; return r === 0 ? 0.5 : (c.close - c.low) / r; }

// ===================================================================
// FULL FEATURE COMPUTATION — INSTITUTIONAL GRADE
// ===================================================================
function computeInstitutionalFeatures(quotes, ti, niftyReturn50d) {
    const { EMA, RSI, ADX, ATR, OBV, MFI, VWAP, PSAR, IchimokuCloud, SMA } = ti;
    if (!quotes || quotes.length < 50) return null;

    const closePrices = quotes.map(q => q.close);
    const highPrices = quotes.map(q => q.high);
    const lowPrices = quotes.map(q => q.low);
    const volumes = quotes.map(q => q.volume);
    const today = quotes[quotes.length - 1];
    const prev = quotes[quotes.length - 2];
    if (!today?.close || !prev?.close) return null;

    // Skip penny stocks and illiquid stocks
    if (today.close < 5) return null; // below ₹5
    const avgVol20 = volumes.slice(-21, -1).reduce((a, b) => a + b, 0) / 20;
    if (avgVol20 < 50000) return null; // less than 50k avg daily volume = illiquid
    const turnover = today.close * avgVol20;
    if (turnover < 5000000) return null; // less than ₹50L daily turnover = skip

    // BASIC 
    const return1d = (today.close - prev.close) / prev.close;
    const return5d = quotes.length >= 6 ? (today.close - quotes[quotes.length - 6].close) / quotes[quotes.length - 6].close : 0;
    const todayCS = closeStrength(today);
    const isBullishCandle = today.close > today.open;
    const bodySize = Math.abs(today.close - today.open) / (today.high - today.low || 1);
    const brokeAbovePrevHigh = today.close > prev.high;
    const volumeRatio = avgVol20 > 0 ? today.volume / avgVol20 : 1;
    const vol3Rising = quotes.length >= 4 && quotes[quotes.length - 1].volume > quotes[quotes.length - 2].volume && quotes[quotes.length - 2].volume > quotes[quotes.length - 3].volume;

    // ATR 
    const sf = (arr) => arr.length > 0 ? arr[arr.length - 1] : null;
    const atrVals = ATR.calculate({ high: highPrices, low: lowPrices, close: closePrices, period: 14 });
    const atr = sf(atrVals) || today.close * 0.02;
    const atrPct = atr / today.close;

    // RSI 
    const rsi = sf(RSI.calculate({ period: 14, values: closePrices })) || 50;

    // EMA STACK 
    const ema9 = sf(EMA.calculate({ period: 9, values: closePrices })) || today.close;
    const ema21 = sf(EMA.calculate({ period: 21, values: closePrices })) || today.close;
    const ema50 = sf(EMA.calculate({ period: Math.min(50, closePrices.length - 1), values: closePrices })) || today.close;
    let emaStack = 0;
    if (ema9 > ema21) emaStack++;
    if (ema21 > ema50) emaStack++;
    if (today.close > ema9) emaStack++;

    // ADX 
    let adx = 20, pdi = 20, mdi = 20;
    try { const v = ADX.calculate({ high: highPrices, low: lowPrices, close: closePrices, period: 14 }); if (v.length > 0) { const d = v[v.length - 1]; adx = d.adx || 20; pdi = d.pdi || 20; mdi = d.mdi || 20; } } catch { }

    // OBV 
    let obvTrend = 0;
    try { const o = OBV.calculate({ close: closePrices, volume: volumes }); if (o.length >= 6) { obvTrend = o[o.length - 6] !== 0 ? (o[o.length - 1] - o[o.length - 6]) / Math.abs(o[o.length - 6]) : 0; } } catch { }

    // CMF 
    const cmf = computeCMF(quotes, 20);

    // MFI 
    let mfi = 50;
    try { const v = MFI.calculate({ high: highPrices, low: lowPrices, close: closePrices, volume: volumes, period: 14 }); mfi = sf(v) || 50; } catch { }

    // AVWAP 
    const swLowIdx = findSwingLowIdx(quotes, 30);
    const avwapVal = computeAVWAP(quotes, swLowIdx);
    const avwapDist = (today.close - avwapVal) / avwapVal;

    // SUPERTREND 
    const supertrend = computeSupertrend(quotes);

    // PSAR 
    let psarBullish = false;
    try { const p = PSAR.calculate({ high: highPrices, low: lowPrices, step: 0.02, max: 0.2 }); psarBullish = p.length > 0 && today.close > p[p.length - 1]; } catch { }

    // BB SQUEEZE 
    const bbData = detectBBSqueeze(ti, closePrices);

    // BB-VWAP Reclaim Strategy Integration (Adapted for Swing trading)
    let hasBBVWAPReclaim = false;
    let bbToday = null;
    try {
        const bbVals = BollingerBands.calculate({ period: 20, values: closePrices, stdDev: 2 });
        if (bbVals && bbVals.length >= 5) {
            bbToday = bbVals[bbVals.length - 1];
            const bbYesterday = bbVals[bbVals.length - 2];
            const bbPrev2 = bbVals[bbVals.length - 3];
            const bbPrev3 = bbVals[bbVals.length - 4];

            const qToday = quotes[quotes.length - 1];
            const qYesterday = quotes[quotes.length - 2];
            const qPrev2 = quotes[quotes.length - 3];
            const qPrev3 = quotes[quotes.length - 4];

            // 1. Oversold condition: Price was below or near the lower Bollinger Band in the previous 3 days
            const threshold = 1.005; // 0.5% buffer zone
            const oversoldPrev1 = qYesterday.close <= bbYesterday.lower * threshold || qYesterday.open <= bbYesterday.lower * threshold;
            const oversoldPrev2 = qPrev2.close <= bbPrev2.lower * threshold || qPrev2.open <= bbPrev2.lower * threshold;
            const oversoldPrev3 = qPrev3.close <= bbPrev3.lower * threshold || qPrev3.open <= bbPrev3.lower * threshold;

            // 2. Liquidity Sweep: Current low or yesterday's low breaks the low of previous days (sweep of recent support)
            const sweepLow = qToday.low < Math.min(qYesterday.low, qPrev2.low) || qYesterday.low < Math.min(qPrev2.low, qPrev3.low);

            // 3. Reclaim confirmation: Today's open above lower BB, close above lower BB, and close above AVWAP or 9 EMA
            const reclaimBB = qToday.open > bbToday.lower && qToday.close > bbToday.lower;
            const reclaimEMA9 = qToday.close > ema9;
            const reclaimAVWAP = qToday.close > avwapVal;

            if ((oversoldPrev1 || oversoldPrev2 || oversoldPrev3) && sweepLow && reclaimBB && (reclaimEMA9 || reclaimAVWAP)) {
                hasBBVWAPReclaim = true;
            }
        }
    } catch (e) {
        console.error("BB-VWAP calculation error:", e);
    }

    // ICHIMOKU 
    let ichiAboveCloud = false;
    try { const v = IchimokuCloud.calculate({ high: highPrices, low: lowPrices, close: closePrices, conversionPeriod: 9, basePeriod: 26, spanPeriod: 52, displacement: 26 }); if (v.length > 0) { const ic = v[v.length - 1]; ichiAboveCloud = today.close > Math.max(ic.spanA || 0, ic.spanB || 0); } } catch { }

    // NARROW RANGE 
    const nr = detectNarrowRange(quotes);

    // 52-WEEK HIGH 
    const high52w = Math.max(...quotes.map(q => q.high));
    const distFrom52wHigh = (today.close - high52w) / high52w;
    const near52wHigh = distFrom52wHigh > -0.05;

    // 
    // INSTITUTIONAL SIGNALS (the ones that matter)
    // 
    const rs50d = computeRelativeStrength(quotes, niftyReturn50d, Math.min(50, quotes.length - 2));
    const vcp = detectVCP(quotes);
    const pocketPivot = detectPocketPivot(quotes);
    const tightClose = detectTightClose(quotes, 5);
    const accIntensity = computeAccumulationIntensity(quotes, 10);
    const forceIdx = computeForceIndex(quotes, 13);
    const stageData = detectStage(quotes, ti);

    // PIVOTS & FIB 
    const pivots = computePivots(today);
    const sw30L = Math.min(...quotes.slice(-30).map(q => q.low));
    const sw30H = Math.max(...quotes.slice(-30).map(q => q.high));
    const fib = computeFib(sw30L, sw30H);
    const support = Math.min(...quotes.slice(-10).map(q => q.low));
    const resistance = Math.max(...quotes.slice(-10).map(q => q.high));

    // TRADE LEVELS 
    const entry = today.close;
    let slATR = entry - atr * 1.5, slSupp = support - atr * 0.3;
    let slFib = fib.l618 < entry ? fib.l618 : slATR;
    let stopLoss = Math.max(slATR, slSupp, slFib);

    // If it's a BB-VWAP Reclaim, place tight stop below the sweep low
    if (hasBBVWAPReclaim && bbToday) {
        const sweepLowVal = Math.min(today.low, prev.low);
        stopLoss = Math.max(sweepLowVal - atr * 0.2, entry * 0.95);
    }

    const slPct = Math.max(0.5, ((entry - stopLoss) / entry) * 100);
    const risk = entry - stopLoss;
    let tgt1 = entry + risk * 2;
    let tgt2 = Math.max(entry + risk * 3, resistance + atr * 0.5, fib.ext1272, pivots.r2);

    // For BB-VWAP Reclaim, first target is middle band, second target is upper band
    if (hasBBVWAPReclaim && bbToday) {
        tgt1 = Math.max(bbToday.middle, entry + risk * 1.5);
        tgt2 = Math.max(bbToday.upper, entry + risk * 3);
    }

    const tgt1Pct = ((tgt1 - entry) / entry) * 100;
    const tgt2Pct = ((tgt2 - entry) / entry) * 100;

    return {
        cmp: today.close, open: today.open, dayHigh: today.high, dayLow: today.low,
        volume: today.volume, avgVolume: avgVol20, turnover,
        return1d, return5d, todayCS, isBullishCandle, bodySize, brokeAbovePrevHigh,
        volumeRatio, vol3Rising, atr, atrPct, rsi,
        emaStack, ema9, ema21, ema50, adx, pdi, mdi,
        focusIdx: forceIdx, obvTrend, cmf, mfi, avwapVal, avwapDist,
        supertrend, psarBullish, bbData, ichiAboveCloud, nr,
        near52wHigh, distFrom52wHigh,
        // INSTITUTIONAL
        rs50d, vcp, pocketPivot, tightClose, accIntensity, forceIdx, stageData,
        pivots, fib, support, resistance,
        entry, stopLoss, slPct, tgt1, tgt1Pct, tgt2, tgt2Pct,
        hasBBVWAPReclaim,
    };
}

// ===================================================================
// SCORING — INTRADAY (tomorrow)
// ===================================================================
function scoreTomorrowIntraday(f) {
    if (!f || f.return1d < -0.04) return null;
    const s = [];

    // BB-VWAP Reclaim Strategy Signal
    s.push({
        name: 'BB-VWAP Reclaim', bullish: f.hasBBVWAPReclaim, weight: 1.8,
        tech: 'Price swept recent swing lows and reclaimed both the lower Bollinger Band and AVWAP/EMA9',
        simple: f.hasBBVWAPReclaim ? 'Reclaimed lower Bollinger Band and key volume level after sweeping the lows — high probability mean-reversion bounce setup.' : 'Did not meet the BB-VWAP reclaim criteria'
    });

    // --- INSTITUTIONAL SIGNALS (higher weight) ---
    s.push({
        name: 'Pocket Pivot', bullish: f.pocketPivot, weight: 1.6,
        tech: f.pocketPivot ? 'Up-day volume exceeds max down-day volume of last 10 sessions' : 'No pocket pivot',
        simple: f.pocketPivot ? ' Today\'s buying volume crushed all recent selling volume — stealth institutional buying detected. This is what hedge funds look for.' : ' No stealth buying signal detected'
    });

    s.push({
        name: 'Accumulation', bullish: f.accIntensity > 0.3, weight: 1.5,
        tech: `Accumulation intensity: ${f.accIntensity.toFixed(2)} (volume-weighted close positioning)`,
        simple: f.accIntensity > 0.3 ? ` Smart money accumulation score: ${f.accIntensity.toFixed(1)} — institutions are systematically buying near the close with heavy volume` : ' No clear accumulation pattern'
    });

    s.push({
        name: 'Close Strength', bullish: f.todayCS > 0.75, weight: 1.5,
        tech: `Closed at ${(f.todayCS * 100).toFixed(0)}% of day's range`,
        simple: f.todayCS > 0.75 ? ` Stock closed in the top ${(100 - f.todayCS * 100).toFixed(0)}% of today — buyers held control till the last minute. Tomorrow opens strong.` : ` Close wasn't convincing — buyers didn't finish strong`
    });

    s.push({
        name: 'RS Ranking', bullish: f.rs50d > 1.2, weight: 1.4,
        tech: `50-day RS vs Nifty: ${f.rs50d.toFixed(2)}x`,
        simple: f.rs50d > 1.2 ? ` Stock is ${f.rs50d.toFixed(1)}x stronger than Nifty 50 over 50 days — it outperforms the market. AMCs buy stocks with high RS.` : ' Not significantly outperforming the market'
    });

    s.push({
        name: 'Stage 2 Trend', bullish: f.stageData.stage === 2, weight: 1.3,
        tech: `Weinstein Stage ${f.stageData.stage} — ${['', 'Basing', 'ADVANCING', 'Topping', 'Declining'][f.stageData.stage]}`,
        simple: f.stageData.stage === 2 ? ' In Stage 2 (Advancing) — this is the ONLY stage worth buying. Price above rising 150-day average. Professional traders only buy Stage 2.' : ` Stage ${f.stageData.stage} — not in the optimal buying stage`
    });

    s.push({
        name: 'Force Index', bullish: f.forceIdx > 0, weight: 1.2,
        tech: `13-day Force Index: ${(f.forceIdx / 1e6).toFixed(1)}M`,
        simple: f.forceIdx > 0 ? ' Buying force is dominant — price moves UP with heavy volume behind it' : ' Selling force dominates — volume behind downward moves'
    });

    s.push({
        name: 'Tight Close Range', bullish: f.tightClose.isTight, weight: 1.3,
        tech: `${f.tightClose.streak} consecutive days closing in top 30% of range`,
        simple: f.tightClose.isTight ? ` ${f.tightClose.streak} days in a row the stock closed near its high — controlled institutional buying. Springs tend to release upward.` : ' No tight closing pattern'
    });

    // --- VOLUME SIGNALS ---
    s.push({
        name: 'Volume Surge', bullish: f.volumeRatio > 1.5, weight: 1.3,
        tech: `Volume ${f.volumeRatio.toFixed(1)}x vs 20-day average`,
        simple: f.volumeRatio > 1.5 ? ` ${f.volumeRatio.toFixed(1)}x higher volume than normal — when big players move, volume rises first. Tomorrow often follows through.` : ' Normal volume — no unusual interest'
    });

    s.push({
        name: 'OBV Accumulation', bullish: f.obvTrend > 0.02, weight: 1.1,
        tech: `OBV trend +${(f.obvTrend * 100).toFixed(1)}% over 5 days`,
        simple: f.obvTrend > 0.02 ? ' On-Balance Volume rising — volume consistently flowing IN on up-days' : ' Volume flow neutral or negative'
    });

    s.push({
        name: 'CMF Inflow', bullish: f.cmf > 0.05, weight: 1.0,
        tech: `CMF: ${f.cmf.toFixed(3)}`,
        simple: f.cmf > 0.05 ? ' 20-day Chaikin Money Flow positive — sustained institutional inflow' : ' Money flow weak or negative'
    });

    // --- PRICE ACTION ---
    s.push({
        name: 'NR Expansion', bullish: f.nr.isNR4 || f.nr.isNR7, weight: 1.2,
        tech: `${f.nr.isNR7 ? 'NR7' : f.nr.isNR4 ? 'NR4' : 'Normal'} pattern`,
        simple: f.nr.isNR4 || f.nr.isNR7 ? ` Today had the narrowest range in ${f.nr.isNR7 ? '7' : '4'} days — a compressed spring. Tomorrow should see a BIG expansion move.` : ' Normal range — no compression'
    });

    s.push({
        name: 'Breakout', bullish: f.brokeAbovePrevHigh, weight: 1.1,
        tech: f.brokeAbovePrevHigh ? 'Closed above previous session high' : 'Within range',
        simple: f.brokeAbovePrevHigh ? ' Broke above yesterday\'s high and held — supply at that level is absorbed. Follow-through likely tomorrow.' : ' Still within previous range'
    });

    s.push({
        name: 'AVWAP Support', bullish: f.avwapDist > 0, weight: 1.0,
        tech: `${(f.avwapDist * 100).toFixed(1)}% above Anchored VWAP`,
        simple: f.avwapDist > 0 ? ' Price above institutional cost basis (AVWAP) — institutions will defend this level' : ' Below institutional average — potential selling pressure'
    });

    s.push({
        name: 'Supertrend', bullish: f.supertrend.isBullish, weight: 0.9,
        tech: `Supertrend: ${f.supertrend.isBullish ? 'BUY' : 'SELL'}`,
        simple: f.supertrend.isBullish ? ' Supertrend says uptrend intact' : ' Supertrend signals downtrend'
    });

    s.push({
        name: 'ATR Volatility', bullish: f.atrPct > 0.025, weight: 0.8,
        tech: `ATR ${(f.atrPct * 100).toFixed(1)}% of price`,
        simple: f.atrPct > 0.025 ? ` Moves ${(f.atrPct * 100).toFixed(1)}% daily — enough range for profitable intraday trades` : ' Too slow for meaningful intraday moves'
    });

    return s;
}

// ===================================================================
// SCORING — SWING (multi-day)
// ===================================================================
function scoreTomorrowSwing(f) {
    if (!f || f.return5d < -0.08) return null;
    const s = [];

    // BB-VWAP Reclaim Strategy Signal
    s.push({
        name: 'BB-VWAP Reclaim', bullish: f.hasBBVWAPReclaim, weight: 1.8,
        tech: 'Price swept recent swing lows and reclaimed both the lower Bollinger Band and AVWAP/EMA9',
        simple: f.hasBBVWAPReclaim ? 'Reclaimed lower Bollinger Band and key volume level after sweeping the lows — high probability mean-reversion bounce setup.' : 'Did not meet the BB-VWAP reclaim criteria'
    });

    // --- INSTITUTIONAL SIGNALS ---
    s.push({
        name: 'VCP Pattern', bullish: f.vcp.isVCP, weight: 1.7,
        tech: `${f.vcp.contractions} contracting pullbacks detected — ${f.vcp.isVCP ? 'VCP CONFIRMED' : 'No VCP'}`,
        simple: f.vcp.isVCP ? ` Volatility Contraction Pattern detected! ${f.vcp.contractions} pullbacks each shallower than the last — sellers are exhausted. Mark Minervini uses this to find 100%+ winners.` : ' No VCP pattern — pullbacks not contracting'
    });

    s.push({
        name: 'RS Ranking', bullish: f.rs50d > 1.5, weight: 1.5,
        tech: `50-day RS vs Nifty: ${f.rs50d.toFixed(2)}x`,
        simple: f.rs50d > 1.5 ? ` ${f.rs50d.toFixed(1)}x stronger than Nifty 50 — institutional-grade relative strength. Mutual funds screen for stocks that beat the index.` : ' RS not strong enough vs market'
    });

    s.push({
        name: 'Stage 2 Advance', bullish: f.stageData.stage === 2, weight: 1.4,
        tech: `Weinstein Stage ${f.stageData.stage}`,
        simple: f.stageData.stage === 2 ? ' Stage 2 ADVANCING — the only stage worth holding for swing trades. Price running above rising 150-day moving average.' : ` Not in Stage 2 — swing risk is higher`
    });

    s.push({
        name: 'Accumulation', bullish: f.accIntensity > 0.2, weight: 1.4,
        tech: `10-day accumulation intensity: ${f.accIntensity.toFixed(2)}`,
        simple: f.accIntensity > 0.2 ? ` Volume-weighted accumulation score of ${f.accIntensity.toFixed(1)} — big players are systematically building positions over the past 2 weeks` : ' No sustained accumulation'
    });

    s.push({
        name: 'Pocket Pivot', bullish: f.pocketPivot, weight: 1.3,
        tech: f.pocketPivot ? 'Pocket pivot detected today' : 'No pocket pivot',
        simple: f.pocketPivot ? ' Pocket Pivot buy signal — developed by O\'Neil\'s top disciples. Signals stealth institutional entry.' : ' No pocket pivot today'
    });

    s.push({
        name: 'Tight Close', bullish: f.tightClose.isTight, weight: 1.3,
        tech: `${f.tightClose.streak}-day consecutive strong closes`,
        simple: f.tightClose.isTight ? ` ${f.tightClose.streak} consecutive closes near day highs — this is textbook institutional accumulation seen before major breakouts` : ' No tight close pattern'
    });

    s.push({
        name: 'Force Index', bullish: f.forceIdx > 0, weight: 1.1,
        tech: `13-period Force Index: ${(f.forceIdx / 1e6).toFixed(1)}M`,
        simple: f.forceIdx > 0 ? ' Elder Force Index positive — price movement backed by volume force' : ' Negative force — selling pressure'
    });

    // --- STRUCTURE ---
    s.push({
        name: 'BB Squeeze', bullish: f.bbData.isSqueeze, weight: 1.4,
        tech: `BB width ${(f.bbData.width * 100).toFixed(1)}% — ${f.bbData.isSqueeze ? 'SQUEEZE' : 'normal'}`,
        simple: f.bbData.isSqueeze ? ' Bollinger Bands at historic tightness — volatility is about to EXPLODE. With bullish signals, this breakout goes UP.' : ' No squeeze — bands normal'
    });

    s.push({
        name: '52W High', bullish: f.near52wHigh, weight: 1.2,
        tech: `${(f.distFrom52wHigh * 100).toFixed(1)}% from 52-week high`,
        simple: f.near52wHigh ? ' Within 5% of 52-week high — stocks near highs break higher. Resistance becomes support.' : ' Far from 52-week high'
    });

    s.push({
        name: 'AVWAP', bullish: f.avwapDist > 0, weight: 1.0,
        tech: `${(f.avwapDist * 100).toFixed(1)}% above AVWAP`,
        simple: f.avwapDist > 0 ? ' Above institutional VWAP — institutions in profit, will support price' : ' Below institutional cost basis'
    });

    s.push({
        name: 'OBV', bullish: f.obvTrend > 0.03, weight: 1.0,
        tech: `OBV trend +${(f.obvTrend * 100).toFixed(1)}%`,
        simple: f.obvTrend > 0.03 ? ' 5-day On-Balance Volume rising — consistent accumulation' : ' No accumulation in volume'
    });

    s.push({
        name: 'CMF', bullish: f.cmf > 0.05, weight: 0.9,
        tech: `CMF: ${f.cmf.toFixed(3)}`,
        simple: f.cmf > 0.05 ? ' 20-day money flow positive — sustained buying' : ' Weak money flow'
    });

    s.push({
        name: 'Supertrend', bullish: f.supertrend.isBullish, weight: 0.9,
        tech: `Supertrend: ${f.supertrend.isBullish ? 'BUY' : 'SELL'}`,
        simple: f.supertrend.isBullish ? ' Supertrend confirms uptrend' : ' Supertrend bearish'
    });

    s.push({
        name: 'Ichimoku', bullish: f.ichiAboveCloud, weight: 0.9,
        tech: `Price ${f.ichiAboveCloud ? 'above' : 'below'} cloud`,
        simple: f.ichiAboveCloud ? ' Above cloud — bullish zone' : ' Below cloud — uncertain'
    });

    s.push({
        name: '5-Day Momentum', bullish: f.return5d > 0.02 && f.return5d < 0.15, weight: 0.8,
        tech: `5-day return: ${(f.return5d * 100).toFixed(1)}%`,
        simple: f.return5d > 0.02 && f.return5d < 0.15 ? ` Up ${(f.return5d * 100).toFixed(1)}% in 5 days — building but not peaked` : ` Momentum not in sweet spot`
    });

    return s;
}

// ===================================================================
// SCORE
// ===================================================================
function scoreSignals(signals) {
    if (!signals) return null;
    let bW = 0, tW = 0, bN = 0;
    for (const s of signals) { tW += s.weight; if (s.bullish) { bW += s.weight; bN++; } }
    const prob = Math.min(0.95, Math.max(0.05, bW / tW));
    return { probability: prob, confidence: bN / signals.length >= 0.75 ? 'HIGH' : bN / signals.length >= 0.55 ? 'MEDIUM' : 'LOW', bullishCount: bN, totalCount: signals.length };
}

function makeSummary(f, score, mode) {
    const { probability: p, bullishCount: bc, totalCount: tc } = score;
    const inst = [
        f.hasBBVWAPReclaim && 'BB-VWAP Reclaim',
        f.pocketPivot && 'Pocket Pivot',
        f.vcp.isVCP && 'VCP pattern',
        f.tightClose.isTight && `${f.tightClose.streak}-day tight close`,
        f.accIntensity > 0.3 && 'strong accumulation',
        f.rs50d > 1.5 && `RS ${f.rs50d.toFixed(1)}x vs Nifty`,
        f.stageData.stage === 2 && 'Stage 2 Advance',
    ].filter(Boolean).join(', ');

    if (mode === 'intraday') {
        if (p >= 0.70) return ` Premium setup for tomorrow. ${bc}/${tc} signals bullish. Institutional signals: ${inst || 'volume + close strength'}. Volume ${f.volumeRatio.toFixed(1)}x above average, close strength ${(f.todayCS * 100).toFixed(0)}%. High probability of strong opening.`;
        if (p >= 0.55) return ` Solid candidate for tomorrow. ${bc}/${tc} signals. ${inst || 'Decent volume and price action'}. Worth adding to tomorrow's watchlist.`;
        return ` Showing early signals (${bc}/${tc}). ${inst || 'Some indicators aligning'}. Monitor for more confirmation.`;
    } else {
        if (p >= 0.70) return ` Institutional-grade swing setup. ${bc}/${tc} signals aligned. ${inst || 'Strong multi-day structure'}. This setup has 15%+ potential over 1-3 weeks.`;
        if (p >= 0.55) return ` Building swing setup. ${bc}/${tc} bullish with ${inst || 'improving trend structure'}. Consider partial entry near AVWAP (₹${f.avwapVal.toFixed(0)}).`;
        return ` Early stage setup (${bc}/${tc}). ${inst || 'Needs more signals'}. Keep on watchlist.`;
    }
}

function clampNumber(value, min, max) {
    return Math.min(max, Math.max(min, Number.isFinite(value) ? value : min));
}

function roundNumber(value, digits = 2) {
    if (!Number.isFinite(value)) return 0;
    return parseFloat(value.toFixed(digits));
}

function buildNextDayAnalysis(f, score, signals, mode) {
    const bullishNames = signals.filter(s => s.bullish).map(s => s.name);
    const liquidityScore = clampNumber(Math.log10(Math.max(f.turnover, 1)) / 9, 0, 1);
    const sevenPctFit = clampNumber(1 - Math.abs((f.tgt2Pct || 0) - 7) / 7, 0, 1);
    const trendScore = clampNumber((f.emaStack / 3) * 0.35 + (f.adx / 45) * 0.3 + (f.rs50d / 3) * 0.35, 0, 1);
    const orderFlowScore = clampNumber(
        (f.volumeRatio / 3) * 0.28 +
        f.todayCS * 0.28 +
        (f.accIntensity + 1) / 2 * 0.2 +
        (f.pocketPivot ? 0.14 : 0) +
        (f.tightClose.isTight ? 0.1 : 0),
        0,
        1
    );
    const emotionalScore = clampNumber(
        (f.return1d > 0 ? 0.18 : -0.08) +
        (f.return5d > 0 ? 0.18 : -0.08) +
        (f.bbData.isSqueeze ? 0.16 : 0) +
        (f.vcp.isVCP ? 0.14 : 0) +
        (f.volumeRatio > 1.8 ? 0.18 : f.volumeRatio > 1.2 ? 0.1 : 0) +
        (f.rsi > 55 && f.rsi < 76 ? 0.16 : f.rsi >= 76 ? 0.06 : 0),
        0,
        1
    );
    const explosiveScore = clampNumber(
        score.probability * 0.26 +
        sevenPctFit * 0.18 +
        orderFlowScore * 0.22 +
        trendScore * 0.16 +
        emotionalScore * 0.12 +
        liquidityScore * 0.06,
        0,
        0.99
    );

    let setupType = 'Structured momentum continuation';
    if (f.hasBBVWAPReclaim) setupType = 'Mean-reversion reclaim after liquidity sweep';
    else if (f.bbData.isSqueeze) setupType = 'Volatility squeeze expansion';
    else if (f.vcp.isVCP) setupType = 'VCP breakout compression';
    else if (f.pocketPivot) setupType = 'Pocket pivot institutional accumulation';

    const emotionalState =
        emotionalScore >= 0.72 ? 'Hot positive attention with breakout fuel' :
        emotionalScore >= 0.52 ? 'Constructive optimism' :
        emotionalScore >= 0.35 ? 'Neutral watch' :
        'Low emotional push';

    return {
        pipeline_stage: 'top50_to_top5_next_day',
        target_move_pct: roundNumber(f.tgt2Pct, 1),
        seven_pct_fit: roundNumber(sevenPctFit, 2),
        explosive_score: roundNumber(explosiveScore, 3),
        setup_type: setupType,
        top_reasons: bullishNames.slice(0, 5),
        instrument_analysis: {
            trend_quality: roundNumber(trendScore, 2),
            liquidity_score: roundNumber(liquidityScore, 2),
            order_flow_score: roundNumber(orderFlowScore, 2),
            volatility_state: f.bbData.isSqueeze ? 'Compressed - expansion candidate' : `${roundNumber(f.atrPct * 100, 2)}% ATR`,
            tape_read: `Close strength ${roundNumber(f.todayCS * 100, 0)}%, volume ${roundNumber(f.volumeRatio, 2)}x, ADX ${roundNumber(f.adx, 1)}.`,
        },
        company_analysis: {
            quality_proxy: f.stageData.stage === 2 && f.rs50d > 1 ? 'Leadership / advancing stage' : f.stageData.stage === 1 ? 'Base building' : 'Needs confirmation',
            order_book_proxy: `No live order book feed in this API. Proxy uses volume ratio, close location, pocket pivot, Force Index, and CMF.`,
            delivery_style_proxy: f.accIntensity > 0.3 || f.cmf > 0.05 ? 'Accumulation leaning' : 'No strong delivery-style accumulation proxy',
            participation_risk: f.turnover < 20000000 ? 'Thin participation risk' : f.turnover > 500000000 ? 'Institutional liquidity' : 'Tradable liquidity',
        },
        emotion_analysis: {
            state: emotionalState,
            score: roundNumber(emotionalScore, 2),
            catalyst_needed: emotionalScore < 0.5,
            risk_note: f.rsi >= 76 ? 'Momentum is crowded; use tighter trailing risk.' : 'No extreme crowding flag from price-volume data.',
        },
    };
}

// ===================================================================
// PRE-FILTER: Yahoo Finance movers
// ===================================================================
async function getActiveMovers(axios) {
    const movers = new Set();
    for (const scrId of ['day_gainers', 'most_actives', 'small_cap_gainers']) {
        try {
            const r = await axios.get(`https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=false&lang=en-IN&region=IN&scrIds=${scrId}&count=200`,
                { headers: { 'User-Agent': 'Mozilla/5.0' }, timeout: 10000 }).catch(() => null);
            if (r?.data?.finance?.result?.[0]?.quotes) {
                for (const q of r.data.finance.result[0].quotes) {
                    const s = q.symbol || '';
                    if (s.endsWith('.NS')) movers.add(s.replace('.NS', ''));
                    else if (s.endsWith('.BO')) movers.add(s.replace('.BO', ''));
                }
            }
        } catch { }
    }
    return Array.from(movers);
}

function isTradableNseSymbol(symbol) {
    if (!symbol || typeof symbol !== 'string') return false;
    const s = symbol.trim().toUpperCase();
    if (s.length < 2 || s.length > 24) return false;
    if (!/^[A-Z]/.test(s)) return false;
    if (!/^[A-Z0-9&-]+$/.test(s)) return false;
    if (/^\d/.test(s) || /^N\d/.test(s)) return false;
    return true;
}

async function getOfficialNSEEquities(axios) {
    if (!axios) return [];
    try {
        const response = await axios.get('https://archives.nseindia.com/content/equities/EQUITY_L.csv', {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/csv,*/*',
            },
            timeout: 12000,
        });

        const rows = String(response.data || '').split(/\r?\n/).filter(Boolean);
        const out = [];
        for (let i = 1; i < rows.length; i++) {
            const parts = rows[i].split(',');
            const symbol = (parts[0] || '').trim().toUpperCase();
            const name = (parts[1] || symbol).trim();
            const series = (parts[2] || '').trim().toUpperCase();
            if (series === 'EQ' && isTradableNseSymbol(symbol)) {
                out.push({ symbol, name, exchange: 'NSE', source: 'NSE_EQUITY_L' });
            }
        }
        console.log(` Official NSE equity list: ${out.length} EQ symbols`);
        return out;
    } catch (e) {
        console.warn(` NSE equity-list scrape failed: ${e.message}`);
        return [];
    }
}

let nseCookie = '';
async function getNseCookie(axios) {
    if (nseCookie) return nseCookie;
    const r = await axios.get('https://www.nseindia.com', {
        headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        timeout: 10000,
    });
    const cookies = r.headers?.['set-cookie'] || [];
    nseCookie = Array.isArray(cookies) ? cookies.map(c => c.split(';')[0]).join('; ') : '';
    return nseCookie;
}

async function fetchNseQuoteIntel(symbol, axios) {
    if (!axios || !isTradableNseSymbol(symbol)) return null;
    try {
        const cookie = await getNseCookie(axios);
        const headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json,text/plain,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': `https://www.nseindia.com/get-quotes/equity?symbol=${encodeURIComponent(symbol)}`,
            ...(cookie ? { Cookie: cookie } : {}),
        };
        const [quoteRes, tradeRes] = await Promise.all([
            axios.get(`https://www.nseindia.com/api/quote-equity?symbol=${encodeURIComponent(symbol)}`, { headers, timeout: 10000 }).catch(() => null),
            axios.get(`https://www.nseindia.com/api/quote-equity?symbol=${encodeURIComponent(symbol)}&section=trade_info`, { headers, timeout: 10000 }).catch(() => null),
        ]);
        const q = quoteRes?.data || {};
        const t = tradeRes?.data || {};
        const depth = q.marketDeptOrderBook || t.marketDeptOrderBook || {};
        const tradeInfo = t.marketDeptOrderBook?.tradeInfo || t.tradeInfo || q.marketDeptOrderBook?.tradeInfo || {};
        const securityInfo = q.securityInfo || {};
        return {
            industry: q.info?.industry || q.metadata?.industry || null,
            trading_status: securityInfo.tradingStatus || q.metadata?.status || null,
            surveillance: securityInfo.surveillance?.surv || securityInfo.surveillance || null,
            total_buy_qty: depth.totalBuyQuantity ?? null,
            total_sell_qty: depth.totalSellQuantity ?? null,
            delivery_qty: tradeInfo.deliveryQuantity ?? null,
            delivery_to_traded_pct: tradeInfo.deliveryToTradedQuantity ?? null,
            traded_volume: tradeInfo.totalTradedVolume ?? q.priceInfo?.totalTradedVolume ?? null,
            free_float_market_cap: tradeInfo.ffmc ?? null,
        };
    } catch {
        return null;
    }
}

async function enrichTopCandidatesWithNseIntel(stocks, axios) {
    if (!axios || !stocks?.length) return;
    const BATCH_SIZE = 5;
    for (let i = 0; i < stocks.length; i += BATCH_SIZE) {
        const batch = stocks.slice(i, i + BATCH_SIZE);
        await Promise.allSettled(batch.map(async (stock) => {
            const intel = await fetchNseQuoteIntel(stock.symbol, axios);
            if (!intel) return;
            stock.nse_intel = intel;
            const buyQty = Number(intel.total_buy_qty || 0);
            const sellQty = Number(intel.total_sell_qty || 0);
            const bookText = buyQty || sellQty
                ? `NSE depth snapshot: buy qty ${buyQty || '-'}, sell qty ${sellQty || '-'}${buyQty && sellQty ? `, buy/sell ${(buyQty / Math.max(1, sellQty)).toFixed(2)}x` : ''}.`
                : stock.next_day_analysis.company_analysis.order_book_proxy;
            const deliveryText = intel.delivery_to_traded_pct != null
                ? `NSE delivery-to-traded ${Number(intel.delivery_to_traded_pct).toFixed(1)}%; ${Number(intel.delivery_to_traded_pct) >= 45 ? 'strong delivery participation' : 'moderate delivery participation'}.`
                : stock.next_day_analysis.company_analysis.delivery_style_proxy;
            stock.next_day_analysis.company_analysis = {
                ...stock.next_day_analysis.company_analysis,
                industry: intel.industry || stock.next_day_analysis.company_analysis.industry,
                order_book_proxy: bookText,
                delivery_style_proxy: deliveryText,
                nse_trading_status: intel.trading_status || 'NSE status unavailable',
            };
        }));
    }
}

// ===================================================================
// GET NIFTY 50 RETURN (for relative strength)
// ===================================================================
async function getNiftyReturn(yahooFinance) {
    try {
        const hist = await yahooFinance.chart('^NSEI', {
            period1: new Date(Date.now() - 100 * 86400000).toISOString(), interval: '1d'
        });
        const q = hist.quotes.filter(q => q.close);
        if (q.length >= 51) {
            return (q[q.length - 1].close - q[q.length - 51].close) / q[q.length - 51].close;
        }
        if (q.length >= 10) {
            const idx = Math.max(0, q.length - 50);
            return (q[q.length - 1].close - q[idx].close) / q[idx].close;
        }
    } catch { }
    return 0.05; // fallback: assume 5% Nifty return
}

// ===================================================================
// EXTRACT ALL NSE EQUITY SYMBOLS FROM INSTRUMENTS
// ===================================================================
function getAllNSESymbols(instruments) {
    const syms = new Set();
    for (const inst of instruments) {
        const exchange = String(inst.exchange || '').toUpperCase();
        if ((exchange === 'NSE' || exchange.startsWith('NSE_')) && isTradableNseSymbol(inst.symbol)) {
            syms.add(inst.symbol.trim().toUpperCase());
        }
    }
    return Array.from(syms);
}

// Massive fallback universe — covers large, mid, small, micro cap stocks
const HARDCODED_UNIVERSE = [
    // NIFTY 50
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL", "ITC", "LT", "BAJFINANCE",
    "MARUTI", "SUNPHARMA", "NTPC", "TATAMOTORS", "POWERGRID", "TITAN", "BAJAJFINSV", "HCLTECH", "WIPRO",
    "ONGC", "COALINDIA", "ADANIPORTS", "ULTRACEMCO", "NESTLEIND", "DRREDDY", "CIPLA", "DIVISLAB",
    "EICHERMOT", "HINDALCO", "JSWSTEEL", "TECHM", "HEROMOTOCO", "BPCL", "GRASIM", "TRENT", "ASIANPAINT",
    "AXISBANK", "KOTAKBANK", "HINDUNILVR", "M&MFIN", "TATASTEEL", "APOLLOHOSP", "ADANIENT",
    // NIFTY NEXT 50
    "SIEMENS", "HAL", "ABB", "ZOMATO", "JIOFIN", "VBL", "TATACONSUM", "DABUR", "MARICO", "GODREJCP",
    "PIDILITIND", "BIOCON", "BERGEPAINT", "HAVELLS", "VOLTAS", "JUBLFOOD", "PFC", "RECLTD", "NHPC",
    "INDIGO", "NAUKRI", "DMART", "COLPAL", "BOSCHLTD", "ACC", "AMBUJACEM", "SBICARD", "IRCTC", "PIIND",
    "CHOLAFIN", "SHRIRAMFIN", "MUTHOOTFIN", "BANKBARODA", "CANBK", "PNB", "IDFCFIRSTB", "FEDERALBNK",
    // MID CAPS (Nifty Midcap 100+ popular)
    "SUZLON", "IREDA", "RVNL", "IRFC", "MAZDOCK", "COCHINSHIP", "HUDCO", "NBCC", "OLECTRA", "JSWINFRA",
    "ANGELONE", "CDSL", "BSE", "PAYTM", "PERSISTENT", "COFORGE", "LTTS", "MPHASIS", "POLYCAB", "DEEPAKNTR",
    "ASTRAL", "LALPATHLAB", "AUROPHARMA", "ALKEM", "TORNTPHARM", "TATAELXSI", "HAPPSTMNDS", "KPITTECH",
    "SJVN", "MANAPPURAM", "BANDHANBNK", "TATAPOWER", "ADANIGREEN", "ADANIPOWER", "BHEL", "BEL", "GAIL",
    "IOC", "SAIL", "HINDPETRO", "INDHOTEL", "PAGEIND", "TRENT", "ZYDUSLIFE", "GLENMARK", "LUPIN",
    "SUNTV", "CROMPTON", "CUMMINSIND", "BHARATFORG", "MRF", "BALKRISIND", "APOLLOTYRE", "EXIDEIND",
    // SMALL CAPS (Nifty Smallcap + popular)
    "RBLBANK", "ABFRL", "IDFC", "DELTACORP", "GMRAIRPORT", "ADANIENSOL", "JINDALSAW", "RATNAMANI",
    "TRIVENI", "GRINDWELL", "MASTEK", "TANLA", "ROUTE", "METROPOLIS", "SYNGENE", "NATCO", "CAPLIPOINT",
    "MOREPENLAB", "GRANULES", "SUDARSCHEM", "FINEORG", "PRAJIND", "TIINDIA", "CEATLTD", "THERMAX",
    "KEC", "KALPATPOWR", "JKCEMENT", "RAMCOCEM", "DALBHARAT", "NUVOCO", "HEIDELBERG", "JK", "STARCEMENT",
    "AFFLE", "LATENTVIEW", "INTELLECT", "SONATSOFTW", "BIRLASOFT", "ZENSAR", "DATAMATICS", "TATACOMM",
    "NAVINFLUOR", "AARTI", "ATUL", "CLEAN", "GNFC", "DEEPAKFERT", "CHAMBAL", "COROMANDEL", "UPL",
    "VGUARD", "KAJARIACER", "CENTURYTEX", "ASTRAZEN", "GLAXO", "PFIZER", "SANOFI", "ABBOTINDIA",
    // MICRO CAPS / MULTIBAGGERS
    "KALYANKJIL", "TATAINVEST", "TV18BRDCST", "NETWORK18", "HFCL", "ITI", "RAILTEL", "IRCON", "NCC",
    "WELSPUNLIV", "RAYMOND", "ARVIND", "TRIDENT", "GOKEX", "KSB", "ELGIEQUIP", "BECTORFOOD", "CCL",
    "RADICO", "UNITDSPR", "EIDPARRY", "SHREECEM", "STARHEALTH", "NIACL", "GICRE", "SBILIFE", "HDFCLIFE",
    "ICICIPRULI", "MAXHEALTH", "FORTIS", "ASTER", "YATHARTH", "MEDPLUS", "VIJAYA", "LAURUSLABS",
    "IPCALAB", "AJANTPHARM", "SUNPHARMA", "DRREDDY", "TORNTPOWER", "CESC", "TATAPOWER", "JSL",
    "GPPL", "IGL", "MGL", "GSPL", "TATACHEM", "SRF", "FLUOROCHEM", "ALKYLAMINE", "IONEXCHANG",
    // F&O STOCKS (high activity)
    "ABCAPITAL", "AUBANK", "BALRAMCHIN", "BATAINDIA", "BDL", "CANFINHOME", "CUB", "ESCORTS",
    "EXIDEIND", "HINDCOPPER", "IDEA", "INDIAMART", "INDUSTOWER", "LICHSGFIN", "M&M", "MFSL",
    "NAM_INDIA", "NATIONALUM", "OBEROIRLTY", "PRESTIGE", "PVRINOX", "RAMCOCEM", "SOLARINDS",
    "TATACHEM", "UBL", "VEDL", "ZEEL", "MCX", "METROPOLIS", "MUTHOOTFIN"
];

// ===================================================================
// MAIN SCREENER 
// ===================================================================
async function runProScreener(mode, yahooFinance, ti, instruments, _unused, axios, maxStocks = 600) {
    const results = [];

    // Step 1: Get Nifty return for RS calculation
    const niftyReturn50d = await getNiftyReturn(yahooFinance);
    console.log(` Nifty 50-day return: ${(niftyReturn50d * 100).toFixed(1)}%`);

    // Step 2: Build MASSIVE universe from official NSE list, instruments, active movers and hardcoded fallbacks
    const allNSE = getAllNSESymbols(instruments);
    console.log(` Total NSE equity symbols from instruments: ${allNSE.length}`);

    let officialNSE = [];
    if (axios) { try { officialNSE = await getOfficialNSEEquities(axios); } catch { } }

    let activeSymbols = [];
    if (axios) { try { activeSymbols = await getActiveMovers(axios); console.log(` ${activeSymbols.length} active movers from Yahoo`); } catch { } }

    const nameBySymbol = new Map();
    for (const inst of instruments || []) {
        if (inst.symbol && inst.name) nameBySymbol.set(String(inst.symbol).toUpperCase(), inst.name);
    }
    for (const inst of officialNSE) nameBySymbol.set(inst.symbol, inst.name);

    // Merge: Active movers and liquid fallbacks first, then the full NSE official/instrument universe.
    const merged = [...new Set([
        ...activeSymbols,
        ...HARDCODED_UNIVERSE,
        ...officialNSE.map(s => s.symbol),
        ...allNSE,
    ].filter(isTradableNseSymbol))];


    // We'll scan up to maxStocks stocks per run for coverage (default 600, Vercel passes 200)
    const toScan = merged.slice(0, maxStocks);
    console.log(` Scanning ${toScan.length} stocks for tomorrow's ${mode} picks...`);

    let scanned = 0, skippedLiq = 0, skippedData = 0;

    // Run processing in parallel batches to dramatically speed up execution and prevent serverless timeouts
    const BATCH_SIZE = 25;
    for (let i = 0; i < toScan.length; i += BATCH_SIZE) {
        const batch = toScan.slice(i, i + BATCH_SIZE);
        await Promise.allSettled(batch.map(async (sym) => {
            try {
                const hist = await yahooFinance.chart(`${sym}.NS`, {
                    period1: new Date(Date.now() - 400 * 86400000).toISOString(), interval: '1d'
                });
                if (!hist?.quotes) { skippedData++; return; }
                const q = hist.quotes.filter(q => q.volume != null && q.close != null && q.open != null);
                if (q.length < 50) { skippedData++; return; }

                const f = computeInstitutionalFeatures(q, ti, niftyReturn50d);
                if (!f) { skippedLiq++; return; }

                scanned++;
                const signals = mode === 'intraday' ? scoreTomorrowIntraday(f) : scoreTomorrowSwing(f);
                if (!signals) return;

                const score = scoreSignals(signals);
                if (!score || score.probability < 0.42) return;

                const inst = instruments.find(i => String(i.symbol).toUpperCase() === sym);
                const summary = makeSummary(f, score, mode);
                const bullish = signals.filter(s => s.bullish).map(s => ({ name: s.name, tech: s.tech, simple: s.simple }));
                const bearish = signals.filter(s => !s.bullish).map(s => ({ name: s.name, tech: s.tech, simple: s.simple }));
                const nextDayAnalysis = buildNextDayAnalysis(f, score, signals, mode);

                let category = 'Micro Cap';
                if (f.turnover > 500000000) category = 'Large Cap';
                else if (f.turnover > 100000000) category = 'Mid Cap';
                else if (f.turnover > 20000000) category = 'Small Cap';

                results.push({
                    symbol: sym,
                    name: inst ? inst.name : (nameBySymbol.get(sym) || sym),
                    market: 'NSE',
                    category,
                    probability: parseFloat(score.probability.toFixed(3)),
                    confidence: score.confidence,
                    confluence: `${score.bullishCount}/${score.totalCount}`,
                    simple_summary: summary,
                    next_day_analysis: nextDayAnalysis,
                    trade_levels: {
                        entry: parseFloat(f.entry.toFixed(2)),
                        target: parseFloat(f.tgt2.toFixed(2)),
                        partial_target: parseFloat(f.tgt1.toFixed(2)),
                        stop_loss: parseFloat(f.stopLoss.toFixed(2)),
                        target_pct: parseFloat(f.tgt2Pct.toFixed(1)),
                        partial_pct: parseFloat(f.tgt1Pct.toFixed(1)),
                        sl_pct: parseFloat(f.slPct.toFixed(1)),
                        risk_reward: parseFloat((f.tgt2Pct / Math.max(0.1, f.slPct)).toFixed(1)),
                        pivot_r1: parseFloat(f.pivots.r1.toFixed(2)),
                        pivot_s1: parseFloat(f.pivots.s1.toFixed(2)),
                        fib_382: parseFloat(f.fib.l382.toFixed(2)),
                        fib_618: parseFloat(f.fib.l618.toFixed(2)),
                        avwap: parseFloat(f.avwapVal.toFixed(2)),
                    },
                    bullish_signals: bullish,
                    bearish_signals: bearish,
                    metrics: {
                        cmp: parseFloat(f.cmp.toFixed(2)),
                        volume_ratio: parseFloat(f.volumeRatio.toFixed(2)),
                        rsi: parseFloat(f.rsi.toFixed(1)),
                        ema_alignment: parseFloat((f.emaStack / 3).toFixed(2)),
                        adx: parseFloat(f.adx.toFixed(1)),
                        atr_pct: parseFloat((f.atrPct * 100).toFixed(2)),
                        cmf: parseFloat(f.cmf.toFixed(3)),
                        mfi: parseFloat(f.mfi.toFixed(1)),
                        obv_trend: parseFloat((f.obvTrend * 100).toFixed(1)),
                        supertrend: f.supertrend.isBullish ? 'BUY' : 'SELL',
                        ichimoku: f.ichiAboveCloud ? 'ABOVE CLOUD' : 'BELOW CLOUD',
                        close_strength: parseFloat((f.todayCS * 100).toFixed(0)),
                        narrow_range: f.nr.isNR7 ? 'NR7' : f.nr.isNR4 ? 'NR4' : 'Normal',
                        bb_squeeze: f.bbData.isSqueeze ? 'YES' : 'NO',
                        bb_vwap_reclaim: f.hasBBVWAPReclaim,
                        rs_ranking: parseFloat(f.rs50d.toFixed(2)),
                        stage: f.stageData.stage,
                        pocket_pivot: f.pocketPivot,
                        vcp: f.vcp.isVCP,
                        acc_intensity: parseFloat(f.accIntensity.toFixed(2)),
                        force_index: parseFloat((f.forceIdx / 1e6).toFixed(2)),
                        tight_close: f.tightClose.streak,
                    },
                });
            } catch { }
        }));
    }

    results.sort((a, b) => {
        const aExplosive = a.next_day_analysis?.explosive_score || 0;
        const bExplosive = b.next_day_analysis?.explosive_score || 0;
        if (bExplosive !== aExplosive) return bExplosive - aExplosive;
        return b.probability - a.probability;
    });
    const watchlist50 = results.slice(0, 50);
    await enrichTopCandidatesWithNseIntel(watchlist50, axios);
    const best5 = watchlist50.slice(0, 5);

    console.log(` Done. Scanned ${scanned} qualified stocks (${skippedLiq} illiquid, ${skippedData} no data). Found ${results.length} setups.`);

    const now = new Date();
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + (now.getDay() === 5 ? 3 : now.getDay() === 6 ? 2 : 1));
    const tomorrowStr = tomorrow.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'short' });

    return {
        mode,
        for_date: tomorrowStr,
        generated_at: new Date().toISOString(),
        model_version: '5.0.0',
        universe_scanned: toScan.length,
        qualified_scanned: scanned,
        indicators_used: 16,
        results_count: best5.length,
        watchlist_count: watchlist50.length,
        results: best5,
        watchlist50,
        disclaimer: `Two-stage next-session analysis for ${tomorrowStr}. The engine scans the available NSE universe, filters to a top-50 watchlist, enriches top candidates with NSE public quote/trade-info data when available, then ranks the best 5 using technical structure, instrument liquidity, order-flow, company quality, delivery-style, and emotional momentum proxies. Educational analysis only, NOT financial advice.`,
    };
}


