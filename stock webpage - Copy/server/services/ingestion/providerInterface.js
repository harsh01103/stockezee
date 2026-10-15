/**
 * Base class for all data providers.
 * Enforces a strict contract for data acquisition.
 */
export class DataProvider {
    constructor(name, priority, supportsIntraday = false) {
        this.name = name;
        this.priority = priority; // Lower number = higher priority
        this.supportsIntraday = supportsIntraday;
    }

    /**
     * Fetch historical OHLCV data for a given symbol.
     * @param {string} symbol - The canonical symbol (e.g., RELIANCE)
     * @param {Date} startDate - The start date for the data
     * @param {Date} endDate - The end date for the data
     * @returns {Promise<Array>} Array of OHLCV objects
     */
    async fetchHistoricalOHLCV(symbol, startDate, endDate) {
        throw new Error(`fetchHistoricalOHLCV not implemented in ${this.name}`);
    }

    /**
     * Test if the provider is currently available (rate limits, network, etc.)
     * @returns {Promise<boolean>}
     */
    async isAvailable() {
        throw new Error(`isAvailable not implemented in ${this.name}`);
    }
}

/**
 * Manages data acquisition by coordinating multiple providers based on priority.
 */
export class DataAcquisitionManager {
    constructor() {
        this.providers = [];
    }

    registerProvider(provider) {
        if (!(provider instanceof DataProvider)) {
            throw new Error("Must register an instance of DataProvider");
        }
        this.providers.push(provider);
        // Sort providers by priority (ascending)
        this.providers.sort((a, b) => a.priority - b.priority);
    }

    /**
     * Tries to fetch historical OHLCV from the highest priority available provider.
     */
    async fetchHistoricalOHLCV(symbol, startDate, endDate) {
        const errors = [];

        for (const provider of this.providers) {
            try {
                const available = await provider.isAvailable();
                if (!available) {
                    console.warn(`[DataAcquisitionManager] Provider ${provider.name} is unavailable. Skipping.`);
                    continue;
                }

                console.log(`[DataAcquisitionManager] Attempting fetch for ${symbol} using ${provider.name}`);
                const data = await provider.fetchHistoricalOHLCV(symbol, startDate, endDate);
                
                // Add provenance data
                const normalizedData = data.map(record => ({
                    ...record,
                    source: provider.name,
                    retrieved_at: new Date().toISOString(),
                    confidence: provider.priority === 1 ? 1.0 : (provider.priority === 2 ? 0.8 : 0.5)
                }));
                
                return normalizedData;
            } catch (err) {
                console.error(`[DataAcquisitionManager] Error with provider ${provider.name}:`, err.message);
                errors.push({ provider: provider.name, error: err.message });
            }
        }

        console.error(`[DataAcquisitionManager] All providers failed for ${symbol}`, errors);
        throw new Error(`Failed to acquire data for ${symbol}. All fallback providers exhausted.`);
    }
}
