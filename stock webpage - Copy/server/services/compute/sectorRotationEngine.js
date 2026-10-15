/**
 * Sector Rotation Engine
 * Evaluates sector strength relative to the broader market to identify where money is flowing.
 */

export class SectorRotationEngine {
    
    /**
     * Compute a sector's relative strength and rotation score.
     * @param {Array<number>} sectorReturns Array of daily sector returns
     * @param {Array<number>} marketReturns Array of daily NIFTY 50 returns
     * @returns {Object} { sectorRS, rotationTrend, score }
     */
    static evaluateSector(sectorReturns, marketReturns) {
        const n = Math.min(sectorReturns.length, marketReturns.length);
        if (n < 60) return { score: 50 }; // Need enough history

        // Construct cumulative indices from returns
        const sectorIndex = [100];
        const marketIndex = [100];
        
        for (let i = 1; i < n; i++) {
            sectorIndex.push(sectorIndex[i-1] * (1 + sectorReturns[i]));
            marketIndex.push(marketIndex[i-1] * (1 + marketReturns[i]));
        }

        // Relative Strength Line (Sector / Market)
        const rsLine = sectorIndex.map((val, i) => val / marketIndex[i]);

        // Calculate slopes of the RS Line
        // 1-month slope (recent momentum)
        const recent20 = rsLine.slice(-20);
        const rsSlope1M = (recent20[19] - recent20[0]) / recent20[0];

        // 3-month slope (structural trend)
        const recent60 = rsLine.slice(-60);
        const rsSlope3M = (recent60[59] - recent60[0]) / recent60[0];

        let score = 50;
        let rotationTrend = 'NEUTRAL';

        if (rsSlope3M > 0.02 && rsSlope1M > 0.01) {
            rotationTrend = 'LEADING';
            score = 90;
        } else if (rsSlope3M < 0 && rsSlope1M > 0.02) {
            rotationTrend = 'IMPROVING'; // Money flowing in recently
            score = 75;
        } else if (rsSlope3M > 0 && rsSlope1M < -0.02) {
            rotationTrend = 'WEAKENING'; // Pullback or distribution
            score = 40;
        } else if (rsSlope3M < -0.02) {
            rotationTrend = 'LAGGING';
            score = 20;
        }

        return {
            rsSlope1M,
            rsSlope3M,
            rotationTrend,
            score
        };
    }
}
