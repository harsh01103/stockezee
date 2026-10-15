/**
 * Model Evaluator
 * Decouples signal prediction from evaluation. Tracks hit rates and confidence accuracy.
 */

export const modelEvaluator = {
    /**
     * Standardize the output format of ML signals
     * @param {Object} rawSignal - Output from mlScreener
     */
    standardizeSignal(rawSignal) {
        return {
            symbol: rawSignal.symbol || 'UNKNOWN',
            strategy: rawSignal.strategy || 'UNKNOWN',
            confidence_score: rawSignal.confidence || 0,
            predicted_move: rawSignal.predicted_move || 0,
            time_horizon: rawSignal.time_horizon || '1D',
            generated_at: new Date().toISOString(),
            metadata: rawSignal.metadata || {}
        };
    },

    /**
     * Evaluate past signals against actual outcomes
     * @param {Array} pastSignals - Array of standardized signals
     * @param {Object} marketData - Actual market data (prices)
     */
    evaluatePerformance(pastSignals, marketData) {
        let hits = 0;
        let total = pastSignals.length;

        const evaluatedSignals = pastSignals.map(signal => {
            const actualMove = marketData[signal.symbol]?.actual_move || 0;
            
            // Hit if predicted move direction matches actual move direction
            const isHit = Math.sign(signal.predicted_move) === Math.sign(actualMove);
            if (isHit) hits++;

            return {
                ...signal,
                actual_move: actualMove,
                is_hit: isHit,
                brier_score: Math.pow((signal.confidence_score / 100) - (isHit ? 1 : 0), 2)
            };
        });

        return {
            hit_rate: total > 0 ? (hits / total) * 100 : 0,
            total_evaluated: total,
            signals: evaluatedSignals
        };
    }
};
