/**
 * Portfolio Risk Engine
 * Implements a centralized kill-switch evaluating daily drawdown, sector concentration, and margin limits.
 */

export const riskEngine = {
    /**
     * Evaluate the risk of a new proposed trade against the current portfolio
     * @param {Object} portfolio - Current portfolio state
     * @param {Object} proposedTrade - The new trade to evaluate
     * @returns {Object} { approved: boolean, reason: string }
     */
    evaluateTrade(portfolio, proposedTrade) {
        console.log(`[RiskEngine] Evaluating trade for ${proposedTrade.symbol}...`);

        const {
            dailyDrawdown = 0,
            maxDailyDrawdown = 5.0, // 5% max daily drawdown
            sectorConcentrations = {},
            maxSectorConcentration = 25.0, // 25% max in one sector
            marginUsed = 0,
            totalEquity = 100000
        } = portfolio;

        // 1. Kill Switch: Daily Drawdown Limit
        if (dailyDrawdown >= maxDailyDrawdown) {
            return {
                approved: false,
                reason: `KILL_SWITCH_ACTIVE: Daily drawdown (${dailyDrawdown}%) exceeds limit (${maxDailyDrawdown}%)`
            };
        }

        // 2. Kill Switch: Sector Concentration Limit
        const sector = proposedTrade.sector || 'UNKNOWN';
        const currentSectorAllocation = sectorConcentrations[sector] || 0;
        const proposedAllocation = (proposedTrade.estimatedValue / totalEquity) * 100;

        if (currentSectorAllocation + proposedAllocation > maxSectorConcentration) {
            return {
                approved: false,
                reason: `CONCENTRATION_LIMIT: Adding ${proposedTrade.symbol} exceeds ${maxSectorConcentration}% limit for ${sector} sector`
            };
        }

        // 3. Margin Limits
        if (marginUsed + proposedTrade.estimatedValue > totalEquity * 0.8) {
            return {
                approved: false,
                reason: `MARGIN_LIMIT: Insufficient margin buffer for trade.`
            };
        }

        return {
            approved: true,
            reason: 'TRADE_APPROVED'
        };
    }
};
