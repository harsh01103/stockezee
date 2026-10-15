/**
 * Trade Replay Store
 * Handles storing and retrieving minute-by-minute candles and chains for historical review.
 */

const mockDb = [];

export const replayStore = {
    /**
     * Store a replay session
     */
    async saveSession(sessionData) {
        console.log(`[ReplayStore] Saving replay session for ${sessionData.symbol}...`);
        const entry = {
            id: crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(),
            ...sessionData,
            created_at: new Date().toISOString()
        };
        mockDb.push(entry);
        return entry;
    },

    /**
     * Retrieve a replay session for the UI
     */
    async getSession(id) {
        return mockDb.find(s => s.id === id);
    },

    /**
     * List recent replay sessions available
     */
    async listSessions(limit = 10) {
        return mockDb.slice(-limit).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    }
};
