// Execution stream: NO CACHING ALLOWED. Must be broker confirmed.

export const marketExecution = {
    /**
     * Fetch absolute real-time broker confirmed quote for execution.
     */
    async getQuote(instrumentKey, brokerService) {
        try {
            // Strict timeout for execution
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 1500);

            const data = await brokerService(instrumentKey, { signal: controller.signal });
            clearTimeout(timeoutId);

            if (!data || !data.last_price) {
                throw new Error('Invalid broker payload');
            }

            return {
                ...data,
                stream: 'EXECUTION',
                confirmed: true,
                executionTimestamp: Date.now()
            };
        } catch (err) {
            console.error('[MarketExecution] Failed to confirm execution quote:', err.message);
            throw new Error(`Execution aborted: Broker quote unconfirmed (${err.message})`);
        }
    }
};
