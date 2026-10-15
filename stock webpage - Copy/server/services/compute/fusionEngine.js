/**
 * Evidence Fusion Engine v2
 * Combines market regime, stock momentum, technical patterns, fundamentals,
 * sentiment, and sector rotation into a robust 0-100 opportunity score.
 */

export class FusionEngine {
    
    /**
     * Score a setup based on 6 dimensions.
     * @param {Object} data 
     * @param {Object} data.regime { state }
     * @param {Object} data.momentum { rsPercentile (0-100), relVol }
     * @param {Object} data.technical { pattern, isNearPivot, candleQuality (0-100) }
     * @param {Object} data.fundamentals { score (0-100) }
     * @param {Object} data.sector { score (0-100) }
     * @param {Array<Object>} data.facts Array of extracted_facts
     */
    static generateOpportunityScore(data) {
        let score = 0;
        
        // Weights that sum to 1.0 (100 points)
        const weights = {
            regime: 0.10,      // 10 pts
            momentum: 0.25,    // 25 pts
            technical: 0.25,   // 25 pts
            fundamentals: 0.20,// 20 pts
            sector: 0.10,      // 10 pts
            sentiment: 0.10    // 10 pts
        };

        // 1. Regime Score (0-100)
        let regimeScore = 50;
        if (data.regime.state === 'STRONG_RISK_ON') regimeScore = 100;
        else if (data.regime.state === 'RISK_ON') regimeScore = 80;
        else if (data.regime.state === 'RISK_OFF') regimeScore = 0;

        // 2. Momentum Score (0-100)
        let momScore = data.momentum.rsPercentile || 50;
        // Boost if rel volume is high
        if (data.momentum.relVol > 1.5) momScore = Math.min(100, momScore + 10);

        // 3. Technical Score (0-100)
        let techScore = data.technical.quality || data.technical.candleQuality || 50;
        // Add pattern specific boosts
        if (['VCP', 'VCP_BREAKOUT', 'ATH_BREAKOUT', 'CUP_AND_HANDLE', 'NR7', 'NR7_CONTRACTION', 'INSIDE_BAR', 'ASCENDING_TRIANGLE', 'HH_HL_TREND'].includes(data.technical.pattern)) {
            techScore += 15;
        }
        if (data.technical.isNearPivot) techScore += 15;
        techScore = Math.min(100, techScore);

        // 4. Fundamental Score (0-100)
        let fundScore = data.fundamentals ? data.fundamentals.score : 50;

        // 5. Sector Score (0-100)
        let sectorScore = data.sector ? data.sector.score : 50;

        // 6. Sentiment / DocIntel Score (0-100)
        let sentScore = 50;
        if (data.facts && data.facts.length > 0) {
            for (const fact of data.facts) {
                if (fact.metric === 'GUIDANCE_UPDATED' && fact.value === 'YES') sentScore += 30;
                if (fact.metric === 'INSIDER_BUYING') sentScore += 40;
                if (fact.metric === 'FINANCIAL_RESULTS_FILED') sentScore += 10;
            }
        }
        sentScore = Math.min(100, sentScore);

        // Final weighted score
        score = (regimeScore * weights.regime) + 
                (momScore * weights.momentum) + 
                (techScore * weights.technical) + 
                (fundScore * weights.fundamentals) +
                (sectorScore * weights.sector) +
                (sentScore * weights.sentiment);

        // Hard veto: If fundamentals are garbage (heavy loss-making), completely tank the final score
        if (fundScore <= 30) {
            score -= 30;
        }

        return Math.max(0, Math.min(100, score));
    }

    /**
     * Determine Trade Readiness based on Risk/Reward and setup proximity.
     */
    static evaluateReadiness(score, currentPrice, entryTrigger, stopLoss, target) {
        if (score < 50) return 'REJECTED'; // Only accept high-quality setups now that scoring is robust

        const risk = entryTrigger - stopLoss;
        const reward = target - entryTrigger;
        const riskReward = risk > 0 ? reward / risk : 0;

        if (riskReward < 1.5) return 'REJECTED'; // Hard mathematical filter

        const dist = (entryTrigger - currentPrice) / currentPrice;

        if (dist <= 0.01 && dist >= -0.02) {
            return 'READY'; // Breaking out or within 1% of pivot
        } else if (dist > 0.01 && dist <= 0.04) {
            return 'NEAR_TRIGGER'; // 1% to 4% below pivot
        } else if (dist > 0.04 && dist <= 0.15) {
            return 'DEVELOPING'; // Approaching pivot
        } else if (dist < -0.02) {
            return 'EXTENDED'; // Too far above pivot, wait for pullback
        }

        return 'DEVELOPING';
    }

    /**
     * Generates a deterministic, fundamental+technical explanation.
     */
    static generateThesis(data, score, readiness) {
        const lines = [];

        // Primary driver
        if (data.momentum.rsPercentile > 90) {
            lines.push(`Top decile momentum stock showing exceptional relative strength.`);
        }

        // Technical Context
        lines.push(`Constructing a ${data.technical.pattern} setup with a precise pivot at ₹${data.technical.pivot}.`);
        
        if ((data.technical.quality || data.technical.candleQuality || 0) > 70) {
            lines.push(`Recent price action is extremely tight with clean, decisive candles and low volatility.`);
        }

        // Fundamental Context
        if (data.fundamentals && data.fundamentals.score >= 70) {
            lines.push(`Strong fundamental backing (Score: ${data.fundamentals.score}/100) combining profitability and growth.`);
        } else if (data.fundamentals && data.fundamentals.score <= 30) {
            lines.push(`Warning: Trading purely on technicals. Fundamentals are weak (Score: ${data.fundamentals.score}/100).`);
        }

        if (readiness === 'READY') {
            lines.push(`Setup is currently actionable as it approaches the primary breakout level.`);
        }

        return {
            summary: lines.join(' '),
            bulletPoints: lines,
            score: score.toFixed(1)
        };
    }
}
