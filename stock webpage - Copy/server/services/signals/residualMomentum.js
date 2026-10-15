import MLR from 'ml-regression-multivariate-linear';

export class ResidualMomentumEngine {
    /**
     * Calculates point-in-time residual momentum for a stock.
     * Math definition from Blitz, Huij, Martens (2011) adapted for this architecture.
     * 
     * Regresses stock weekly returns against market weekly returns and sector weekly returns
     * over a 36-month window (~156 weeks).
     * The residual momentum is the standardized sum of residuals over the last 6 months (~26 weeks).
     * 
     * @param {Array<number>} stockReturns - Array of weekly stock returns (oldest to newest)
     * @param {Array<number>} marketReturns - Array of weekly market returns (NIFTY 500)
     * @param {Array<number>} sectorReturns - Array of weekly sector returns
     * @returns {Object} Score and diagnostic info
     */
    static calculate(stockReturns, marketReturns, sectorReturns) {
        if (stockReturns.length < 156 || marketReturns.length < 156 || sectorReturns.length < 156) {
            return { error: 'Insufficient history. Requires at least 156 weeks (36 months).' };
        }

        // Align arrays to exactly 156 weeks (tail)
        const sRet = stockReturns.slice(-156);
        const mRet = marketReturns.slice(-156);
        const secRet = sectorReturns.slice(-156);

        // Independent variables X: [MarketReturn, SectorReturn]
        // Dependent variable y: [StockReturn]
        const x = [];
        const y = [];
        for (let i = 0; i < 156; i++) {
            x.push([mRet[i], secRet[i]]);
            y.push([sRet[i]]);
        }

        try {
            const mlr = new MLR(x, y);

            // Calculate residuals for the last 26 weeks (6 months)
            const residuals = [];
            for (let i = 156 - 26; i < 156; i++) {
                const predicted = mlr.predict(x[i])[0];
                const actual = y[i][0];
                residuals.push(actual - predicted);
            }

            // Sum of residuals
            const sumResiduals = residuals.reduce((a, b) => a + b, 0);

            // Standard deviation of the last 26 weeks' residuals
            const meanResidual = sumResiduals / 26;
            const variance = residuals.reduce((acc, val) => acc + Math.pow(val - meanResidual, 2), 0) / 25; // Sample variance
            const stdDevResidual = Math.sqrt(variance);

            if (stdDevResidual === 0) {
                return { error: 'Standard deviation of residuals is 0. Cannot compute score.' };
            }

            // Standardized Residual Momentum score
            const rawScore = sumResiduals / stdDevResidual;

            return {
                rawScore,
                meanResidual,
                stdDevResidual,
                betaMarket: mlr.weights[0][0],
                betaSector: mlr.weights[1][0],
                alpha: mlr.weights[2][0] // Intercept is added last in ml-regression-multivariate-linear usually
            };
        } catch (err) {
            return { error: `Regression failed: ${err.message}` };
        }
    }
}
