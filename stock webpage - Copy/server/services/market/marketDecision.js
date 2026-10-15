import NodeCache from 'node-cache';

// Slower cache for decision/ML models (1 to 5 seconds TTL)
const decisionCache = new NodeCache({ stdTTL: 5, checkperiod: 1 });

export const marketDecision = {
    /**
     * Fetch quote for decision engine. Avoids jitter.
     */
    async getQuote(instrumentKey, fallbackService) {
        const cacheKey = `dec_${instrumentKey}`;
        let data = decisionCache.get(cacheKey);

        if (!data) {
            try {
                // Timeout after 3s to prevent hanging the ML screener
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 3000);
                
                data = await fallbackService(instrumentKey, { signal: controller.signal });
                clearTimeout(timeoutId);

                data.stream = 'DECISION';
                data.reliability = 'HIGH';
                
                decisionCache.set(cacheKey, data);
            } catch (err) {
                console.error('[MarketDecision] Timeout or fetch error:', err.message);
                // Return a structured error fallback for the decision engine
                return { error: true, message: err.message, stream: 'DECISION' };
            }
        }
        return data;
    }
};
