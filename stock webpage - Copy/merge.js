import fs from 'fs';

const tsCode = `
import { VercelRequest, VercelResponse } from "@vercel/node";
// @ts-ignore
import YahooFinance from "yahoo-finance2";
// @ts-ignore
import ti from "technicalindicators";

const yahooFinance = new (YahooFinance as any)();

// Vercel Serverless maximum execution limit
export const maxDuration = 60;

let cache: any = null;
let cacheTime = 0;
const CACHE_TTL = 3600000; // 1 hour

export default async function handler(req: VercelRequest, res: VercelResponse) {
    try {
        const now = Date.now();
        if (cache && (now - cacheTime < CACHE_TTL)) {
            return res.status(200).json(cache);
        }

        console.log('\\n🔬 [VERCEL] Running Institutional-Grade Screener...');

        const instruments: any[] = []; // Used if we don't have CSV on Vercel
        
        // Passing null for axios to skip the yahoo finance active movers on Vercel since it hits memory/time limits
        const [swingResult, intradayResult] = await Promise.all([
            runProScreener('swing', yahooFinance, ti, instruments, null, null, 200).catch((e: any) => {
                console.error('Swing screener error:', e.message);
                return { results: [], for_date: '', disclaimer: '', universe_scanned: 0 };
            }),
            runProScreener('intraday', yahooFinance, ti, instruments, null, null, 200).catch((e: any) => {
                console.error('Intraday screener error:', e.message);
                return { results: [], for_date: '', disclaimer: '', universe_scanned: 0 };
            })
        ]);

        const responsePayload = {
            news: [],
            intradaySetups: swingResult.results || [],
            swingSetups: swingResult.results || [],
            for_date: swingResult.for_date || intradayResult.for_date || '',
            model_version: '5.0.0',
            universe_scanned: Math.max(swingResult.universe_scanned || 0, intradayResult.universe_scanned || 0),
            indicators_used: 16,
            disclaimer: swingResult.disclaimer || intradayResult.disclaimer || 'Educational analysis only.'
        };

        if (responsePayload.swingSetups.length > 0 || responsePayload.intradaySetups.length > 0) {
            cache = responsePayload;
            cacheTime = now;
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
`;

const jsCode = fs.readFileSync('server/mlScreener.js', 'utf8').replace('export { runProScreener };', '');

fs.writeFileSync('api/news.ts', tsCode + '\n\n' + jsCode);
