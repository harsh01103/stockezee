import MLR from 'ml-regression-multivariate-linear';

/**
 * Feature Engine v2
 * Responsible for calculating quantitative metrics: MAs, RS, Breadth, Residual Momentum,
 * plus new indicators: OBV, RSI, Inside Bars, NR7, Weekly aggregation, MA Slope.
 */
export class FeatureEngine {
    
    /**
     * Compute Simple Moving Average
     */
    static computeSMA(prices, period) {
        if (prices.length < period) return null;
        const sum = prices.slice(-period).reduce((a, b) => a + b, 0);
        return sum / period;
    }

    /**
     * Compute Exponential Moving Average
     */
    static computeEMA(prices, period) {
        if (prices.length < period) return null;
        const k = 2 / (period + 1);
        let ema = prices[0]; // Start with the oldest price
        for (let i = 1; i < prices.length; i++) {
            ema = (prices[i] - ema) * k + ema;
        }
        return ema;
    }

    /**
     * Compute Mansfield-style Relative Strength against a benchmark (e.g., Nifty 50)
     * @param {Array<number>} stockPrices 
     * @param {Array<number>} benchmarkPrices 
     * @param {number} days Lookback period 
     */
    static computeRelativeStrength(stockPrices, benchmarkPrices, days) {
        if (stockPrices.length < days + 1 || benchmarkPrices.length < days + 1) return null;
        
        const stockReturn = (stockPrices[stockPrices.length - 1] - stockPrices[stockPrices.length - 1 - days]) / stockPrices[stockPrices.length - 1 - days];
        const benchReturn = (benchmarkPrices[benchmarkPrices.length - 1] - benchmarkPrices[benchmarkPrices.length - 1 - days]) / benchmarkPrices[benchmarkPrices.length - 1 - days];
        
        return (1 + stockReturn) / (1 + benchReturn);
    }

    /**
     * Compute Residual Momentum (Idiosyncratic Alpha)
     * Regresses stock returns against market and sector returns.
     */
    static computeResidualMomentum(stockReturns, marketReturns, sectorReturns) {
        const n = Math.min(stockReturns.length, marketReturns.length, sectorReturns.length);
        if (n < 30) return null;

        const x = [];
        const y = [];
        for (let i = 0; i < n; i++) {
            x.push([marketReturns[i], sectorReturns[i]]);
            y.push([stockReturns[i]]);
        }

        try {
            const mlr = new MLR(x, y);
            const predictions = mlr.predict(x);
            
            let residualSum = 0;
            const residuals = [];
            for (let i = 0; i < n; i++) {
                const res = stockReturns[i] - predictions[i][0];
                residuals.push(res);
                residualSum += res;
            }

            const meanRes = residualSum / n;
            let variance = 0;
            for (let i = 0; i < n; i++) {
                variance += Math.pow(residuals[i] - meanRes, 2);
            }
            const stdDev = Math.sqrt(variance / n) || 1;
            
            const recentResidualSum = residuals.slice(-126).reduce((a, b) => a + b, 0);
            return recentResidualSum / stdDev;
        } catch (err) {
            console.error('[FeatureEngine] MLR calculation failed:', err.message);
            return null;
        }
    }

    /**
     * Compute a cap-weighted or equal-weighted Sector Return index over time.
     */
    static computeSectorReturns(constituentReturnsList) {
        if (!constituentReturnsList || constituentReturnsList.length === 0) return [];
        const length = constituentReturnsList[0].length;
        const sectorReturns = new Array(length).fill(0);

        for (let day = 0; day < length; day++) {
            let sum = 0;
            let count = 0;
            for (let i = 0; i < constituentReturnsList.length; i++) {
                if (constituentReturnsList[i][day] !== undefined && !isNaN(constituentReturnsList[i][day])) {
                    sum += constituentReturnsList[i][day];
                    count++;
                }
            }
            sectorReturns[day] = count > 0 ? sum / count : 0;
        }
        return sectorReturns;
    }

    /**
     * Compute Market Breadth (% of stocks above their N-day DMA)
     */
    static computeMarketBreadth(allStockPrices) {
        let above20 = 0, above50 = 0, above200 = 0;
        let total20 = 0, total50 = 0, total200 = 0;

        for (const stock of allStockPrices) {
            if (stock.sma20 !== null) { total20++; if (stock.close > stock.sma20) above20++; }
            if (stock.sma50 !== null) { total50++; if (stock.close > stock.sma50) above50++; }
            if (stock.sma200 !== null) { total200++; if (stock.close > stock.sma200) above200++; }
        }

        return {
            above20_pct: total20 > 0 ? (above20 / total20) * 100 : 0,
            above50_pct: total50 > 0 ? (above50 / total50) * 100 : 0,
            above200_pct: total200 > 0 ? (above200 / total200) * 100 : 0
        };
    }

    // ═══════════════════════════════════════════════════════
    // NEW v2 INDICATORS
    // ═══════════════════════════════════════════════════════

    /**
     * Compute RSI (Relative Strength Index)
     * @param {Array<number>} prices Close prices
     * @param {number} period RSI period (default 14)
     * @returns {number|null} RSI value 0-100
     */
    static computeRSI(prices, period = 14) {
        if (prices.length < period + 1) return null;

        let avgGain = 0;
        let avgLoss = 0;

        // Initial average gain/loss
        for (let i = prices.length - period; i < prices.length; i++) {
            const change = prices[i] - prices[i - 1];
            if (change > 0) avgGain += change;
            else avgLoss += Math.abs(change);
        }
        avgGain /= period;
        avgLoss /= period;

        if (avgLoss === 0) return 100;
        const rs = avgGain / avgLoss;
        return 100 - (100 / (1 + rs));
    }

    /**
     * Compute On-Balance Volume (OBV)
     * Measures buying/selling pressure via cumulative volume flow.
     * @param {Array<Object>} quotes [{close, volume}]
     * @returns {Array<number>} OBV series
     */
    static computeOBV(quotes) {
        if (quotes.length < 2) return [];
        const obv = [0];
        for (let i = 1; i < quotes.length; i++) {
            if (quotes[i].close > quotes[i - 1].close) {
                obv.push(obv[i - 1] + quotes[i].volume);
            } else if (quotes[i].close < quotes[i - 1].close) {
                obv.push(obv[i - 1] - quotes[i].volume);
            } else {
                obv.push(obv[i - 1]);
            }
        }
        return obv;
    }

    /**
     * Check if OBV is trending upward (accumulation signal)
     * @param {Array<Object>} quotes [{close, volume}]
     * @param {number} lookback Days to check OBV trend
     * @returns {boolean}
     */
    static isOBVRising(quotes, lookback = 20) {
        const obv = this.computeOBV(quotes);
        if (obv.length < lookback) return false;
        
        const recentOBV = obv.slice(-lookback);
        const obvSMA = recentOBV.reduce((a, b) => a + b, 0) / recentOBV.length;
        const obvStart = recentOBV.slice(0, 5).reduce((a, b) => a + b, 0) / 5;
        const obvEnd = recentOBV.slice(-5).reduce((a, b) => a + b, 0) / 5;
        
        return obvEnd > obvStart && recentOBV[recentOBV.length - 1] > obvSMA;
    }

    /**
     * Detect Inside Bar on daily data.
     * An inside bar's high is lower than previous bar's high AND
     * its low is higher than previous bar's low.
     * @param {Array<Object>} quotes [{high, low, open, close}]
     * @returns {Object} { isInsideBar, motherBar, insideBar }
     */
    static detectInsideBar(quotes) {
        if (quotes.length < 2) return { isInsideBar: false };
        
        const curr = quotes[quotes.length - 1];
        const prev = quotes[quotes.length - 2];
        
        const isInsideBar = curr.high < prev.high && curr.low > prev.low;
        
        return {
            isInsideBar,
            motherBar: prev,
            insideBar: curr,
            // Tightness ratio: how compressed is the inside bar relative to mother
            tightnessRatio: isInsideBar ? (curr.high - curr.low) / (prev.high - prev.low) : 1.0
        };
    }

    /**
     * Detect Weekly Inside Bar by aggregating daily data into weekly bars.
     * @param {Array<Object>} dailyQuotes 
     * @returns {Object}
     */
    static detectWeeklyInsideBar(dailyQuotes) {
        const weeklyBars = this.aggregateToWeekly(dailyQuotes);
        if (weeklyBars.length < 2) return { isInsideBar: false };
        return this.detectInsideBar(weeklyBars);
    }

    /**
     * Detect NR7 — Narrowest Range in 7 days.
     * Classic pre-breakout contraction signal.
     * @param {Array<Object>} quotes [{high, low}]
     * @returns {boolean}
     */
    static detectNR7(quotes) {
        if (quotes.length < 7) return false;
        
        const last7 = quotes.slice(-7);
        const ranges = last7.map(q => q.high - q.low);
        const currentRange = ranges[ranges.length - 1];
        
        return currentRange <= Math.min(...ranges);
    }

    /**
     * Detect NR4 — Narrowest Range in 4 days (tighter contraction).
     */
    static detectNR4(quotes) {
        if (quotes.length < 4) return false;
        
        const last4 = quotes.slice(-4);
        const ranges = last4.map(q => q.high - q.low);
        const currentRange = ranges[ranges.length - 1];
        
        return currentRange <= Math.min(...ranges);
    }

    /**
     * Aggregate daily OHLCV data into weekly bars.
     * Week starts on Monday.
     * @param {Array<Object>} dailyQuotes [{date, open, high, low, close, volume}]
     * @returns {Array<Object>} Weekly bars
     */
    static aggregateToWeekly(dailyQuotes) {
        if (!dailyQuotes || dailyQuotes.length === 0) return [];
        
        const weeks = [];
        let currentWeek = null;
        
        for (const day of dailyQuotes) {
            const d = new Date(day.date);
            const weekStart = new Date(d);
            weekStart.setDate(d.getDate() - d.getDay() + 1); // Monday
            const weekKey = weekStart.toISOString().split('T')[0];
            
            if (!currentWeek || currentWeek.weekKey !== weekKey) {
                if (currentWeek) weeks.push(currentWeek);
                currentWeek = {
                    weekKey,
                    date: day.date,
                    open: day.open,
                    high: day.high,
                    low: day.low,
                    close: day.close,
                    volume: day.volume || 0
                };
            } else {
                currentWeek.high = Math.max(currentWeek.high, day.high);
                currentWeek.low = Math.min(currentWeek.low, day.low);
                currentWeek.close = day.close;
                currentWeek.volume += (day.volume || 0);
                currentWeek.date = day.date; // latest date in the week
            }
        }
        if (currentWeek) weeks.push(currentWeek);
        
        return weeks;
    }

    /**
     * Compute the slope of a moving average over a lookback period.
     * Positive slope = uptrend, negative = downtrend.
     * @param {Array<number>} prices
     * @param {number} maPeriod MA period to compute slope for
     * @param {number} slopeLookback How many days of MA values to measure slope over
     * @returns {number|null} Slope as percentage change per day
     */
    static computeMASlope(prices, maPeriod, slopeLookback = 20) {
        if (prices.length < maPeriod + slopeLookback) return null;
        
        // Compute MA at current and at slopeLookback days ago
        const maNow = this.computeSMA(prices, maPeriod);
        const maBack = this.computeSMA(prices.slice(0, -slopeLookback), maPeriod);
        
        if (!maNow || !maBack || maBack === 0) return null;
        return ((maNow - maBack) / maBack) * 100; // percentage change
    }

    /**
     * Check Weinstein Stage 2 conditions:
     * 1. Price above rising 30-week (150-day) MA
     * 2. 30-week MA is rising
     * 3. Price above 200 SMA
     * 4. 50 SMA > 200 SMA (golden cross structure)
     * @param {Array<number>} closes
     * @returns {Object} { isStage2, conditions }
     */
    static checkWeinsteinStage2(closes) {
        if (closes.length < 200) return { isStage2: false, conditions: {} };
        
        const currentPrice = closes[closes.length - 1];
        const sma50 = this.computeSMA(closes, 50);
        const sma150 = this.computeSMA(closes, 150);
        const sma200 = this.computeSMA(closes, 200);
        const sma50Slope = this.computeMASlope(closes, 50, 20);
        const sma150Slope = this.computeMASlope(closes, 150, 20);
        
        const conditions = {
            aboveSMA50: currentPrice > sma50,
            aboveSMA150: currentPrice > sma150,
            aboveSMA200: currentPrice > sma200,
            sma50AboveSMA200: sma50 > sma200,  // Golden cross structure
            sma50Rising: sma50Slope > 0,
            sma150Rising: sma150Slope > 0
        };
        
        const isStage2 = conditions.aboveSMA50 && conditions.aboveSMA150 && 
                         conditions.aboveSMA200 && conditions.sma50AboveSMA200 &&
                         conditions.sma50Rising;
        
        return { isStage2, conditions, sma50, sma150, sma200 };
    }

    /**
     * Compute Relative Volume (current volume vs N-day average)
     * @param {Array<Object>} quotes [{volume}]
     * @param {number} period
     * @returns {number} Ratio (1.5 = 50% above average)
     */
    static computeRelativeVolume(quotes, period = 20) {
        if (quotes.length < period + 1) return 1.0;
        
        const avgVol = quotes.slice(-(period + 1), -1).reduce((sum, q) => sum + q.volume, 0) / period;
        if (avgVol === 0) return 1.0;
        return quotes[quotes.length - 1].volume / avgVol;
    }

    /**
     * Check volume dry-up in base/consolidation.
     * Volume should be declining during the base (accumulation phase).
     * @param {Array<Object>} quotes
     * @param {number} baseDays How many recent days to check
     * @returns {boolean}
     */
    static isVolumeDryingUp(quotes, baseDays = 20) {
        if (quotes.length < baseDays + 20) return false;
        
        const baseVol = quotes.slice(-baseDays).reduce((sum, q) => sum + q.volume, 0) / baseDays;
        const priorVol = quotes.slice(-(baseDays + 20), -baseDays).reduce((sum, q) => sum + q.volume, 0) / 20;
        
        return priorVol > 0 && (baseVol / priorVol) < 0.7; // Volume dropped by at least 30%
    }
}
