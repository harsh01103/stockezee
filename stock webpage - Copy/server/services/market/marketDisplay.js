import NodeCache from 'node-cache';
import axios from 'axios';

// Fast cache for UI Display (100ms TTL for fast ticker feel)
const displayCache = new NodeCache({ stdTTL: 0.25, checkperiod: 0.1 });
let brokerHealth = 'UNKNOWN';

export const marketDisplay = {
    /**
     * Fetch display quote. Uses fast cache (100-250ms)
     */
    async getQuote(instrumentKey, fallbackService) {
        const cacheKey = `disp_${instrumentKey}`;
        let data = displayCache.get(cacheKey);

        if (!data) {
            try {
                // Fetch from the broker/fallbackService
                data = await fallbackService(instrumentKey);
                
                // Add metadata
                data.stream = 'DISPLAY';
                data.latencyMs = Date.now() - (data.lastFetch || Date.now());
                data.brokerHealth = brokerHealth;
                
                // Set cache
                displayCache.set(cacheKey, data);
            } catch (err) {
                console.error('[MarketDisplay] Fetch error:', err.message);
                throw new Error('Display stream unavailable');
            }
        }
        return data;
    },

    setBrokerHealth(status) {
        brokerHealth = status;
    }
};
