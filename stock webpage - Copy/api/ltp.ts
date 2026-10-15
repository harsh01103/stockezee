import { VercelRequest, VercelResponse } from "@vercel/node";
import fetch from "node-fetch";
import { getInstruments } from "./utils.js";
import yahooFinance from "yahoo-finance2";

let ltpCache: any = {};
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
    const { instrument_key } = req.query;

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

    const now = Date.now();
    if (ltpCache[yfSymbol] && (now - ltpCache[yfSymbol].lastFetch) < 3000) {
        const cached = ltpCache[yfSymbol];
        const jitter = 1 + ((Math.random() - 0.5) * 0.0001);
        return res.json({
            ...cached,
            last_price: parseFloat((cached.last_price * jitter).toFixed(2))
        });
    }

    try {
        const yahooRes = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${yfSymbol}?interval=1m&range=1d`, {
            headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' }
        });
        const data = await yahooRes.json();
        const meta = data.chart.result[0].meta;

        let multiplier = 1;
        if (isCommodity) {
            multiplier = await getMCXMultiplier(instrument_key);
        }

        const priceData = {
            last_price: (meta.regularMarketPrice || meta.previousClose) * multiplier,
            dayHigh: (meta.regularMarketDayHigh || meta.regularMarketPrice) * multiplier,
            dayLow: (meta.regularMarketDayLow || meta.regularMarketPrice) * multiplier,
            open: (meta.regularMarketOpen || meta.regularMarketPrice) * multiplier,
            prevClose: meta.previousClose * multiplier,
            volume: meta.regularMarketVolume || 0,
            lastFetch: now
        };
        ltpCache[yfSymbol] = priceData;
        res.status(200).json(priceData);
    } catch (e: any) {
        if (ltpCache[yfSymbol]) {
            return res.json(ltpCache[yfSymbol]);
        }
        console.error("LTP API Error:", e.response?.data || e.message);
        res.status(500).json({ error: e.message });
    }
}
