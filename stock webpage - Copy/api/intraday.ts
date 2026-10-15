import { VercelRequest, VercelResponse } from "@vercel/node";
import fetch from "node-fetch";
import { getInstruments } from "./utils.js";
import yahooFinance from "yahoo-finance2";

let cachedUSDINR = 86.5;
let lastUSDINRFetch = 0;

async function getMCXMultiplier(instrument_key: string) {
    const now = Date.now();
    if (now - lastUSDINRFetch > 600000) {
        try {
            const forex = await yahooFinance.quote('INR=X');
            if (forex && forex.regularMarketPrice) {
                cachedUSDINR = forex.regularMarketPrice;
                lastUSDINRFetch = now;
            }
        } catch (e) { console.error("Forex sync error, using fallback."); }
    }

    let multiplier = 1;
    const preciousMetalPremium = 1.095;
    const crudePremium = 1.002;

    if (instrument_key === 'COMM|GOLD') multiplier = (cachedUSDINR / 3.11) * preciousMetalPremium;
    else if (instrument_key === 'COMM|SILVER') multiplier = (cachedUSDINR * 32.15) * preciousMetalPremium;
    else multiplier = cachedUSDINR * crudePremium;

    return multiplier;
}


export default async function handler(req: VercelRequest, res: VercelResponse) {
    const { instrument_key, interval = "1m" } = req.query;

    if (!instrument_key || typeof instrument_key !== "string") {
        return res.status(400).json({ error: "Missing instrument_key" });
    }

    let yfSymbol = '';
    let isCommodity = false;

    if (instrument_key.startsWith('COMM|')) {
        isCommodity = true;
        if (instrument_key === 'COMM|CRUDEOIL') yfSymbol = 'CL=F';
        else if (instrument_key === 'COMM|NATURALGAS') yfSymbol = 'NG=F';
        else if (instrument_key === 'COMM|GOLD') yfSymbol = 'GC=F';
        else if (instrument_key === 'COMM|SILVER') yfSymbol = 'SI=F';
    } else {
        const instruments = await getInstruments();
        const instrument = instruments.find(i => i.instrument_key === instrument_key);
        if (!instrument) return res.status(404).json({ error: 'Instrument not found' });
        yfSymbol = instrument.symbol;
        if (instrument.exchange === 'NSE_EQ') yfSymbol += '.NS';
        else if (instrument.exchange === 'BSE_EQ') yfSymbol += '.BO';
        else yfSymbol += '.NS';
    }

    const intervalStr = Array.isArray(interval) ? interval[0] : (interval as string);
    let rangeQuery = "1d";

    if (intervalStr === "1m") rangeQuery = "5d";
    else if (["5m", "15m", "30m", "60m", "90m"].includes(intervalStr)) rangeQuery = "1mo";
    else if (intervalStr === "1h") rangeQuery = "3mo";
    else if (intervalStr === "1d") rangeQuery = "1y";

    try {
        const yahooRes = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${yfSymbol}?interval=${intervalStr}&range=${rangeQuery}`, {
            headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' }
        });
        const data = await yahooRes.json();
        const chartData = data.chart.result[0];
        if (!chartData.timestamp || !chartData.indicators.quote[0]) {
            return res.status(200).json([]);
        }

        const timestamps = chartData.timestamp;
        const quotes = chartData.indicators.quote[0];

        let multiplier = 1;
        if (isCommodity) {
            multiplier = await getMCXMultiplier(instrument_key);
        }

        const candles = [];
        for (let i = 0; i < timestamps.length; i++) {
            if (quotes.open[i] !== null && quotes.open[i] !== undefined) {
                candles.push({
                    time: timestamps[i],
                    open: quotes.open[i] * multiplier,
                    high: quotes.high[i] * multiplier,
                    low: quotes.low[i] * multiplier,
                    close: quotes.close[i] * multiplier,
                    volume: quotes.volume[i] || 0
                });
            }
        }

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

        res.status(200).json(candles);
    } catch (e: any) {
        console.error("Intraday API Error:", e.response?.data || e.message);
        res.status(500).json({ error: e.message });
    }
}
