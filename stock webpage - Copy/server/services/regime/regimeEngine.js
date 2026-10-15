/**
 * Market Regime Engine
 * Fetches real NIFTY 50 data, computes EMA slopes, breadth, and volatility
 * to classify the current market environment.
 */

export const REGIMES = {
    STRONG_RISK_ON: 'STRONG_RISK_ON',
    RISK_ON: 'RISK_ON',
    SELECTIVE_BULL: 'SELECTIVE_BULL',
    NEUTRAL: 'NEUTRAL',
    SELECTIVE_BEAR: 'SELECTIVE_BEAR',
    RISK_OFF: 'RISK_OFF'
};

export const regimeEngine = {

    /**
     * Fetch NIFTY 50 OHLCV from Supabase and classify the market regime.
     * This is the primary entry point called by the FusionWorker.
     * @param {Object} supabase - Supabase client instance
     * @returns {Object} { regime_state, nifty_trend_score, breadth_pcts, volatility_percentile }
     */
    async fetchAndClassify(supabase) {
        try {
            // 1. Fetch NIFTY 50 data (use ^NSEI or NIFTY_50 depending on what's in DB)
            const { data: niftyData } = await supabase
                .from('daily_ohlcv')
                .select('date, close, high, low')
                .in('symbol', ['NIFTY_50', '^NSEI'])
                .order('date', { ascending: true })
                .limit(300);

            // 2. Fetch breadth data (latest market_regime row if available)
            const { data: latestBreadth } = await supabase
                .from('market_regime')
                .select('*')
                .order('date', { ascending: false })
                .limit(1);

            // 3. Compute breadth from stock_features if no regime row exists
            let breadthAbove50 = 50; // default neutral
            let breadthAbove200 = 50;

            if (latestBreadth && latestBreadth.length > 0) {
                breadthAbove50 = latestBreadth[0].breadth_above_50dma_pct || 50;
                breadthAbove200 = latestBreadth[0].breadth_above_200dma_pct || 50;
            }

            // 4. Compute NIFTY trend from actual data
            let niftyTrendScore = 50; // neutral default
            let volatilityPercentile = 50;

            if (niftyData && niftyData.length >= 50) {
                const closes = niftyData.map(d => d.close);
                const n = closes.length;

                // EMA 20 and EMA 50
                const ema20 = this._computeEMA(closes, 20);
                const ema50 = this._computeEMA(closes, 50);

                // EMA 20 slope (change over last 10 days)
                const ema20_10ago = this._computeEMA(closes.slice(0, -10), 20);
                const ema20Slope = ema20 && ema20_10ago ? (ema20 - ema20_10ago) / ema20_10ago : 0;

                // Price position relative to EMAs
                const currentPrice = closes[n - 1];
                const aboveEma20 = currentPrice > ema20;
                const aboveEma50 = currentPrice > ema50;
                const ema20AboveEma50 = ema20 > ema50;

                // Trend score: 0 (bearish) to 100 (bullish)
                niftyTrendScore = 50;
                if (aboveEma20) niftyTrendScore += 15;
                if (aboveEma50) niftyTrendScore += 15;
                if (ema20AboveEma50) niftyTrendScore += 10;
                if (ema20Slope > 0.005) niftyTrendScore += 10; // Rising slope
                if (ema20Slope < -0.005) niftyTrendScore -= 10; // Falling slope

                // Realized volatility (20-day)
                const returns = [];
                for (let i = Math.max(1, n - 21); i < n; i++) {
                    returns.push(Math.log(closes[i] / closes[i - 1]));
                }
                const meanReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
                const variance = returns.reduce((sum, r) => sum + Math.pow(r - meanReturn, 2), 0) / returns.length;
                const dailyVol = Math.sqrt(variance);
                const annualizedVol = dailyVol * Math.sqrt(252) * 100; // as percentage

                // Volatility percentile (rough heuristic: NIFTY annual vol ~12-25%)
                // Lower vol = more risk-on, higher vol = more risk-off
                if (annualizedVol < 12) volatilityPercentile = 10;
                else if (annualizedVol < 15) volatilityPercentile = 25;
                else if (annualizedVol < 18) volatilityPercentile = 50;
                else if (annualizedVol < 22) volatilityPercentile = 75;
                else volatilityPercentile = 90;
            }

            // 5. Classify regime
            const regime = this._classifyFromMetrics(niftyTrendScore, breadthAbove50, breadthAbove200, volatilityPercentile);

            // 6. Persist to market_regime
            const today = new Date().toISOString().split('T')[0];
            await supabase.from('market_regime').upsert({
                date: today,
                regime_state: regime,
                nifty_trend_score: niftyTrendScore,
                breadth_above_50dma_pct: breadthAbove50,
                breadth_above_200dma_pct: breadthAbove200,
                volatility_percentile: volatilityPercentile
            }, { onConflict: 'date' });

            return {
                regime_state: regime,
                nifty_trend_score: niftyTrendScore,
                breadth_above_50dma_pct: breadthAbove50,
                breadth_above_200dma_pct: breadthAbove200,
                volatility_percentile: volatilityPercentile
            };

        } catch (err) {
            console.error('[RegimeEngine] Error:', err.message);
            return { regime_state: 'NEUTRAL', nifty_trend_score: 50 };
        }
    },

    /**
     * Classify regime from computed metrics.
     */
    _classifyFromMetrics(trendScore, breadth50, breadth200, volPercentile) {
        // STRONG_RISK_ON: Strong trend + wide breadth + low vol
        if (trendScore >= 85 && breadth50 >= 70 && volPercentile <= 30) {
            return REGIMES.STRONG_RISK_ON;
        }

        // RISK_ON: Good trend + decent breadth
        if (trendScore >= 70 && breadth50 >= 55) {
            return REGIMES.RISK_ON;
        }

        // SELECTIVE_BULL: Trend OK but breadth narrowing
        if (trendScore >= 60 && breadth50 >= 40) {
            return REGIMES.SELECTIVE_BULL;
        }

        // RISK_OFF: Weak trend + low breadth + high vol
        if (trendScore <= 30 && breadth50 <= 35 && volPercentile >= 70) {
            return REGIMES.RISK_OFF;
        }

        // SELECTIVE_BEAR: Weak trend
        if (trendScore <= 40 && breadth50 <= 45) {
            return REGIMES.SELECTIVE_BEAR;
        }

        return REGIMES.NEUTRAL;
    },

    /**
     * Simple EMA computation helper.
     */
    _computeEMA(prices, period) {
        if (!prices || prices.length < period) return null;
        const k = 2 / (period + 1);
        let ema = prices[0];
        for (let i = 1; i < prices.length; i++) {
            ema = (prices[i] - ema) * k + ema;
        }
        return ema;
    },

    /**
     * Legacy synchronous classifier (kept for backward compatibility).
     */
    classifyRegime(marketData) {
        const {
            vix = 15,
            breadthPercent = 60,
            sp500Trend = 'UP',
            atrExpansion = false
        } = marketData;

        if (vix >= 35 && atrExpansion) {
            return { regime: REGIMES.RISK_OFF, confidence: 90 };
        }
        if (vix >= 25 && sp500Trend === 'DOWN') {
            return { regime: REGIMES.SELECTIVE_BEAR, confidence: 85 };
        }
        if (breadthPercent >= 65 && sp500Trend === 'UP' && vix < 20) {
            return { regime: REGIMES.RISK_ON, confidence: 88 };
        }
        return { regime: REGIMES.NEUTRAL, confidence: 70 };
    }
};
