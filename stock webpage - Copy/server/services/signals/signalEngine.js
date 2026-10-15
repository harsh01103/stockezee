import { signalLogger } from './signalLogger.js';

export const signalEngine = {
    /**
     * Evaluate signals for a given symbol and market data
     * @param {string} symbol - Stock symbol
     * @param {object} marketData - Processed market features
     */
    async evaluate(symbol, marketData) {
        console.log(`[SignalEngine] Evaluating ${symbol}...`);
        
        // Mock evaluation logic based on marketData
        const signals = [];

        // Example logic: if price is moving up strong
        if (marketData.momentum > 0.8) {
            signals.push({
                symbol,
                type: 'MOMENTUM_BURST',
                direction: 'BULLISH',
                confidence: 85.5,
                price_at_signal: marketData.ltp || 100,
                timeframe: '1D',
                metadata: { rsi: marketData.rsi, volume_surge: true }
            });
        }

        // Example logic: if VCP pattern detected
        if (marketData.vcpConfirmed) {
            signals.push({
                symbol,
                type: 'VCP_BREAKOUT',
                direction: 'BULLISH',
                confidence: 92.0,
                price_at_signal: marketData.ltp || 100,
                timeframe: '1W',
                metadata: { contractions: 3, rs_rating: 95 }
            });
        }

        // Persist signals
        for (const sig of signals) {
            await signalLogger.log(sig);
        }

        return signals;
    }
};
