// Mock Supabase or Database client
const mockDb = [];

export const signalLogger = {
    /**
     * Persist a generated signal to the database
     */
    async log(signalPayload) {
        try {
            const entry = {
                id: crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(),
                ...signalPayload,
                created_at: new Date().toISOString()
            };
            
            // In a real env, insert into Supabase signal_registry table
            mockDb.push(entry);
            console.log(`[SignalLogger] Persisted ${signalPayload.type} signal for ${signalPayload.symbol}`);
            return entry;
        } catch (err) {
            console.error('[SignalLogger] Failed to log signal:', err.message);
        }
    },

    /**
     * Fetch recent signals for the UI Explorer
     */
    async getRecentSignals(limit = 50) {
        return mockDb.slice(-limit).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    }
};
