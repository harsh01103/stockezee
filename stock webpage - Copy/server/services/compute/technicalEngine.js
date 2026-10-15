/**
 * Technical Engine v2
 * Decoupled moving average, ATR, and technical indicator logic.
 * Computes features sequentially without blocking the main event loop.
 */

export class TechnicalEngine {
    
    /**
     * Compute True Range (TR) and Average True Range (ATR)
     * @param {Array<Object>} quotes [{high, low, close}] 
     * @param {number} period 
     */
    static computeATR(quotes, period = 20) {
        if (quotes.length < period) return null;

        const tr = [];
        for (let i = 1; i < quotes.length; i++) {
            const h = quotes[i].high;
            const l = quotes[i].low;
            const pc = quotes[i - 1].close;
            tr.push(Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc)));
        }

        let atr = tr.slice(0, period).reduce((a, b) => a + b, 0) / period;
        for (let i = period; i < tr.length; i++) {
            atr = (atr * (period - 1) + tr[i]) / period;
        }

        return atr;
    }

    /**
     * Compute Anchored VWAP (AVWAP) from a specific index
     */
    static computeAVWAP(quotes, fromIdx) {
        let cumVP = 0;
        let cumV = 0;
        for (let i = fromIdx; i < quotes.length; i++) {
            const tp = (quotes[i].high + quotes[i].low + quotes[i].close) / 3;
            cumVP += tp * quotes[i].volume;
            cumV += quotes[i].volume;
        }
        return cumV > 0 ? cumVP / cumV : quotes[quotes.length - 1].close;
    }

    /**
     * Compute Chaikin Money Flow (CMF) for institutional accumulation
     */
    static computeCMF(quotes, period = 20) {
        const n = quotes.length;
        if (n < period) return 0;
        let mfv = 0;
        let vol = 0;
        
        for (let i = n - period; i < n; i++) {
            const hl = quotes[i].high - quotes[i].low;
            const mfm = hl > 0 ? ((quotes[i].close - quotes[i].low) - (quotes[i].high - quotes[i].close)) / hl : 0;
            mfv += mfm * quotes[i].volume;
            vol += quotes[i].volume;
        }
        return vol > 0 ? mfv / vol : 0;
    }

    /**
     * Detects Pocket Pivots (Volume on up-day > highest down-volume in last 10 days)
     * @returns {Object} { isPocketPivot, price, volume }
     */
    static detectPocketPivot(quotes) {
        const n = quotes.length;
        if (n < 12) return { isPocketPivot: false };

        const today = quotes[n - 1];
        if (today.close <= today.open) return { isPocketPivot: false }; // Up-day required

        let maxDownVol = 0;
        for (let i = n - 11; i < n - 1; i++) {
            if (quotes[i].close < quotes[i].open) {
                maxDownVol = Math.max(maxDownVol, quotes[i].volume);
            }
        }

        const isPP = today.volume > maxDownVol && maxDownVol > 0;
        return {
            isPocketPivot: isPP,
            price: today.close,
            volume: today.volume
        };
    }

    /**
     * Compute MACD (Moving Average Convergence Divergence)
     * Standard parameters: 12, 26, 9
     */
    static computeMACD(closes, fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) {
        if (closes.length < slowPeriod + signalPeriod) return null;

        const kFast = 2 / (fastPeriod + 1);
        const kSlow = 2 / (slowPeriod + 1);
        
        let emaFast = closes.slice(0, fastPeriod).reduce((a, b) => a + b) / fastPeriod;
        let emaSlow = closes.slice(0, slowPeriod).reduce((a, b) => a + b) / slowPeriod;
        
        const macdLine = [];
        
        for (let i = slowPeriod; i < closes.length; i++) {
            emaFast = (closes[i] - emaFast) * kFast + emaFast;
            emaSlow = (closes[i] - emaSlow) * kSlow + emaSlow;
            macdLine.push(emaFast - emaSlow);
        }

        const kSignal = 2 / (signalPeriod + 1);
        let signalLine = macdLine.slice(0, signalPeriod).reduce((a, b) => a + b) / signalPeriod;
        const histogram = [];

        for (let i = signalPeriod; i < macdLine.length; i++) {
            signalLine = (macdLine[i] - signalLine) * kSignal + signalLine;
            histogram.push(macdLine[i] - signalLine);
        }

        return {
            macd: macdLine[macdLine.length - 1],
            signal: signalLine,
            histogram: histogram[histogram.length - 1]
        };
    }

    /**
     * Compute Candle Quality Score (0-100)
     * High score means decisive candles (large body relative to wicks).
     * Low score means indecisive, doji, or excessive upper wicks (distribution).
     * @param {Array<Object>} quotes Recent candles (e.g., last 5 days)
     */
    static candleQualityScore(quotes) {
        if (quotes.length === 0) return 50;

        let totalScore = 0;
        for (const q of quotes) {
            const range = q.high - q.low;
            if (range === 0) {
                totalScore += 20; // Doji/no-range = poor quality
                continue;
            }

            const body = Math.abs(q.close - q.open);
            const upperWick = q.high - Math.max(q.open, q.close);
            
            const bodyRatio = body / range;
            const upperWickRatio = upperWick / range;

            let score = bodyRatio * 100; // Base score on body size
            
            if (upperWickRatio > 0.4) {
                score -= 30; // Heavy penalty for large upper wicks (selling pressure)
            }
            if (q.close < q.open) {
                score -= 10; // Slight penalty for down-days in the recent cluster
            }
            
            totalScore += Math.max(0, Math.min(100, score));
        }

        return totalScore / quotes.length;
    }

    /**
     * Check if there are any significant gap-downs in recent days.
     * Large gap-downs break structural integrity.
     */
    static hasRecentGapDown(quotes, lookback = 5, gapThreshold = 0.02) {
        if (quotes.length < lookback + 1) return false;
        
        const recent = quotes.slice(-(lookback + 1));
        for (let i = 1; i < recent.length; i++) {
            const gap = (recent[i].open - recent[i - 1].close) / recent[i - 1].close;
            if (gap <= -gapThreshold) {
                return true;
            }
        }
        return false;
    }
}
