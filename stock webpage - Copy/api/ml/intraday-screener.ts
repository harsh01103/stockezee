// Vercel Serverless: ML Intraday Screener
import { VercelRequest, VercelResponse } from "@vercel/node";
import fetch from "node-fetch";

const SCREENING_UNIVERSE = [
    "SUZLON", "IREDA", "RVNL", "IRFC", "HAL", "BSE", "ZOMATO", "PAYTM",
    "JIOFIN", "MAZDOCK", "COCHINSHIP", "HUDCO", "NBCC", "OLECTRA", "JSWINFRA",
    "ANGELONE", "CDSL", "VBL", "RELIANCE", "TCS", "INFY",
    "TATASTEEL", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL", "ITC", "LT",
    "BAJFINANCE", "MARUTI", "SUNPHARMA", "NTPC", "TATAMOTORS", "POWERGRID",
    "TITAN", "BAJAJFINSV", "ASIANPAINT", "HCLTECH", "WIPRO", "ONGC"
];

function sigmoid(x: number, center = 0, scale = 1): number {
    return 1 / (1 + Math.exp(-(x - center) / scale));
}

function computeBasicFeatures(quotes: any[]) {
    if (!quotes || quotes.length < 20) return null;

    const closes = quotes.map((q: any) => q.close);
    const volumes = quotes.map((q: any) => q.volume);
    const latest = quotes[quotes.length - 1];
    const prev = quotes[quotes.length - 2];
    if (!latest?.close || !prev?.close) return null;

    const return1d = (latest.close - prev.close) / prev.close;
    const return5d = quotes.length >= 6 ? (latest.close - quotes[quotes.length - 6].close) / quotes[quotes.length - 6].close : 0;
    const gapPct = (latest.open - prev.close) / prev.close;

    const recentVols = volumes.slice(-21, -1);
    const avgVol = recentVols.length > 0 ? recentVols.reduce((a: number, b: number) => a + b, 0) / recentVols.length : 1;
    const volumeRatio = avgVol > 0 ? latest.volume / avgVol : 1;

    // Simple RSI calc
    let gains = 0, losses = 0;
    const period = Math.min(14, closes.length - 1);
    for (let i = closes.length - period; i < closes.length; i++) {
        const diff = closes[i] - closes[i - 1];
        if (diff > 0) gains += diff;
        else losses += Math.abs(diff);
    }
    const rs = losses === 0 ? 100 : gains / losses;
    const rsi = 100 - (100 / (1 + rs));

    // EMA alignment (simplified)
    const ema = (arr: number[], p: number) => {
        const k = 2 / (p + 1);
        let e = arr[0];
        for (let i = 1; i < arr.length; i++) e = arr[i] * k + e * (1 - k);
        return e;
    };
    const ema9 = ema(closes, 9);
    const ema21 = ema(closes, 21);
    let emaScore = 0;
    if (ema9 > ema21) emaScore += 0.5;
    if (latest.close > ema9) emaScore += 0.5;

    return { return1d, return5d, gapPct, volumeRatio, rsi, emaScore, cmp: latest.close };
}

let cache: any = null;
let cacheTime = 0;

export default async function handler(req: VercelRequest, res: VercelResponse) {
    const now = Date.now();
    if (cache && (now - cacheTime < 600000)) {
        return res.status(200).json(cache);
    }

    const results: any[] = [];

    for (const symbol of SCREENING_UNIVERSE.slice(0, 20)) {
        try {
            const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}.NS?interval=1d&range=3mo`;
            const yahooRes = await fetch(url, {
                headers: { 'User-Agent': 'Mozilla/5.0' }
            });
            const data: any = await yahooRes.json();
            const result = data?.chart?.result?.[0];
            if (!result?.indicators?.quote?.[0]) continue;

            const timestamps = result.timestamp || [];
            const quote = result.indicators.quote[0];
            const quotes = timestamps.map((t: number, i: number) => ({
                close: quote.close[i], open: quote.open[i],
                high: quote.high[i], low: quote.low[i], volume: quote.volume[i]
            })).filter((q: any) => q.close != null);

            const features = computeBasicFeatures(quotes);
            if (!features || features.return1d < -0.02) continue;

            const probability = Math.min(0.95, Math.max(0.05,
                sigmoid(features.volumeRatio, 1.5, 0.5) * 0.25 +
                sigmoid(features.rsi, 60, 10) * 0.15 +
                features.emaScore * 0.2 +
                sigmoid(features.gapPct * 100, 1, 1) * 0.15 +
                sigmoid(features.return1d * 100, 1, 1.5) * 0.15 +
                0.1
            ));

            if (probability < 0.35) continue;

            const factors: string[] = [];
            if (features.volumeRatio > 1.5) factors.push(`Volume ${features.volumeRatio.toFixed(1)}x avg`);
            if (features.emaScore >= 0.8) factors.push('Bullish EMA alignment');
            if (features.rsi >= 55 && features.rsi <= 75) factors.push(`RSI momentum (${features.rsi.toFixed(0)})`);

            results.push({
                symbol, name: symbol, market: 'NSE',
                probability: parseFloat(probability.toFixed(3)),
                confidence: probability >= 0.7 ? 'HIGH' : probability >= 0.5 ? 'MEDIUM' : 'LOW',
                key_factors: factors.slice(0, 3),
                metrics: {
                    cmp: parseFloat(features.cmp.toFixed(2)),
                    volume_ratio: parseFloat(features.volumeRatio.toFixed(2)),
                    rsi: parseFloat(features.rsi.toFixed(1)),
                    ema_alignment: parseFloat(features.emaScore.toFixed(2)),
                    adx: 0, atr_pct: 0,
                    return_1d: parseFloat((features.return1d * 100).toFixed(2)),
                    return_5d: parseFloat((features.return5d * 100).toFixed(2)),
                }
            });
        } catch { continue; }
    }

    results.sort((a, b) => b.probability - a.probability);

    const response = {
        mode: 'intraday',
        generated_at: new Date().toISOString(),
        model_version: '1.0.0',
        universe_size: SCREENING_UNIVERSE.length,
        results_count: results.length,
        results: results.slice(0, 10),
        disclaimer: 'Educational and analytical screening only. Not investment advice.',
    };

    cache = response;
    cacheTime = now;

    res.status(200).json(response);
}
