import { signalLogger } from './signalLogger.js';

export const signalReplay = {
    /**
     * Re-evaluate past signals against forward outcomes
     */
    async evaluateOutcomes(symbol, timeframeDays = 5) {
        console.log(`[SignalReplay] Analyzing outcomes for ${symbol} over ${timeframeDays} days...`);
        const recentSignals = await signalLogger.getRecentSignals(100);
        
        const results = recentSignals.filter(s => s.symbol === symbol).map(sig => {
            // Mock outcome evaluation
            const fakeOutcomePrice = sig.price_at_signal * (1 + (Math.random() * 0.1 - 0.03));
            const success = sig.direction === 'BULLISH' ? fakeOutcomePrice > sig.price_at_signal : fakeOutcomePrice < sig.price_at_signal;
            
            return {
                signal_id: sig.id,
                success,
                peak_return: Math.abs(fakeOutcomePrice - sig.price_at_signal) / sig.price_at_signal * 100
            };
        });

        return results;
    }
};
