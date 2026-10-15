import YahooFinance from 'yahoo-finance2';
const yahooFinance = new YahooFinance();
import { DataProvider } from '../providerInterface.js';

export class YahooFinanceProvider extends DataProvider {
    constructor() {
        super('YahooFinance', 3, true); // Priority 3 (Fallback), supports intraday
    }

    async isAvailable() {
        // Yahoo Finance doesn't have a strict ping, but we can assume it's available 
        // unless we hit a rate limit which we'd catch during fetch.
        return true; 
    }

    async fetchHistoricalOHLCV(symbol, startDate, endDate) {
        // YF expects symbols with suffix for NSE/BSE (e.g. RELIANCE.NS)
        const yfSymbol = symbol.endsWith('.NS') || symbol.endsWith('.BO') ? symbol : `${symbol}.NS`;
        
        const queryOptions = { 
            period1: startDate, 
            period2: endDate, 
            interval: '1d' 
        };

        const result = await yahooFinance.historical(yfSymbol, queryOptions);
        
        if (!result || result.length === 0) {
            return [];
        }

        return result.map(q => ({
            symbol: symbol,
            date: q.date.toISOString().split('T')[0],
            open: q.open,
            high: q.high,
            low: q.low,
            close: q.close,
            volume: q.volume,
            traded_value: q.close * q.volume // Approximation
        }));
    }
}
