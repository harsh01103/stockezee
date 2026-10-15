/**
 * Pattern Engine v2
 * Quantitative chart geometry detection for institutional patterns.
 * Identifies VCP, Flat Bases, Inside Bars, ATH breakouts, Cup & Handle, HH-HL trends.
 */

export class PatternEngine {

    /**
     * Finds structural swing highs and lows in price data.
     */
    static identifySwingPoints(quotes, leftBars = 10, rightBars = 10) {
        const highs = [];
        const lows = [];
        
        for (let i = leftBars; i < quotes.length - rightBars; i++) {
            let isHigh = true;
            let isLow = true;
            
            for (let j = i - leftBars; j <= i + rightBars; j++) {
                if (i === j) continue;
                if (quotes[j].high >= quotes[i].high) isHigh = false;
                if (quotes[j].low <= quotes[i].low) isLow = false;
            }
            
            if (isHigh) highs.push({ index: i, price: quotes[i].high, date: quotes[i].date });
            if (isLow) lows.push({ index: i, price: quotes[i].low, date: quotes[i].date });
        }
        
        return { highs, lows };
    }

    /**
     * Detects Volatility Contraction Pattern (VCP) geometrically.
     * Evaluates strictly: shallower depths from left to right, decreasing volume.
     */
    static detectVCP(quotes) {
        const n = quotes.length;
        if (n < 40) return { isVCP: false, contractions: 0, depths: [] };

        const last40 = quotes.slice(-40);
        const high40 = Math.max(...last40.map(q => q.high));

        let contractions = 0;
        let prevDepth = Infinity;
        let inPullback = false;
        let pullbackLow = high40;
        let avgVolume = last40.reduce((sum, q) => sum + q.volume, 0) / 40;
        let rightSideVolume = 0;
        let rightSideDays = 0;
        const depths = [];

        for (let i = 0; i < last40.length; i++) {
            if (last40[i].close < high40 * 0.97 && !inPullback) {
                inPullback = true;
                pullbackLow = last40[i].low;
                rightSideVolume = 0;
                rightSideDays = 0;
            } else if (inPullback) {
                pullbackLow = Math.min(pullbackLow, last40[i].low);
                rightSideVolume += last40[i].volume;
                rightSideDays++;
                
                if (last40[i].close > high40 * 0.95) {
                    const depth = (high40 - pullbackLow) / high40;
                    depths.push(depth);
                    
                    const localAvgVol = rightSideDays > 0 ? rightSideVolume / rightSideDays : avgVolume;
                    const isVolumeDryUp = localAvgVol < avgVolume * 0.8;
                    
                    if (depth < prevDepth && depth > 0.02 && isVolumeDryUp) {
                        contractions++;
                    }
                    prevDepth = depth;
                    inPullback = false;
                }
            }
        }

        const currentClose = quotes[n - 1].close;
        const nearPivot = currentClose > high40 * 0.95 && currentClose <= high40 * 1.05;

        return { 
            isVCP: contractions >= 2 && nearPivot, 
            contractions,
            depths,
            pivot: high40
        };
    }

    /**
     * Detects Flat Bases
     * Consolidation within a tight range (<15%) for at least 20 days.
     */
    static detectFlatBase(quotes) {
        const n = quotes.length;
        if (n < 25) return { isFlatBase: false };

        const last25 = quotes.slice(-25);
        const maxHigh = Math.max(...last25.map(q => q.high));
        const minLow = Math.min(...last25.map(q => q.low));
        
        const baseDepth = (maxHigh - minLow) / maxHigh;
        
        if (baseDepth < 0.15) {
            return {
                isFlatBase: true,
                baseDepth,
                pivot: maxHigh,
                support: minLow
            };
        }
        return { isFlatBase: false };
    }

    /**
     * Detect All-Time High Breakout or Proximity
     * From the ATH scanner methodology.
     */
    static detectATHBreakout(quotes) {
        if (quotes.length < 250) return { isATH: false }; // Need at least 1 year of data ideally

        // Find highest high in the entire dataset (or last 3 years if too big)
        const lookback = quotes.slice(-750); // ~3 years max
        const ath = Math.max(...lookback.map(q => q.high));
        
        const currentClose = quotes[quotes.length - 1].close;
        const currentHigh = quotes[quotes.length - 1].high;

        const distToATH = (ath - currentClose) / currentClose;

        // Is it breaking out today, or coiling within 3% of ATH?
        if (distToATH <= 0.03 && distToATH >= -0.02) {
            return {
                isATH: true,
                pivot: ath,
                distToATH
            };
        }
        return { isATH: false };
    }

    /**
     * Detect 52-Week High Breakout or Proximity
     */
    static detect52WeekHighProximity(quotes) {
        if (quotes.length < 250) return { is52WHigh: false };

        const lookback = quotes.slice(-250);
        const high52 = Math.max(...lookback.map(q => q.high));
        
        const currentClose = quotes[quotes.length - 1].close;
        const dist = (high52 - currentClose) / currentClose;

        if (dist <= 0.05 && dist >= -0.02) {
            return {
                is52WHigh: true,
                pivot: high52,
                dist
            };
        }
        return { is52WHigh: false };
    }

    /**
     * Detect Cup and Handle Pattern
     */
    static detectCupAndHandle(quotes) {
        const n = quotes.length;
        if (n < 60) return { isCupAndHandle: false }; // Needs at least 3 months

        const last120 = quotes.slice(-120);
        
        // Find left lip of the cup
        const { highs } = this.identifySwingPoints(last120, 10, 10);
        if (highs.length < 2) return { isCupAndHandle: false };

        // Assume the highest swing high is the left lip
        const sortedHighs = [...highs].sort((a, b) => b.price - a.price);
        const leftLip = sortedHighs[0];
        
        // Find the lowest point after the left lip (the bowl)
        const afterLeftLip = last120.slice(leftLip.index);
        if (afterLeftLip.length < 20) return { isCupAndHandle: false }; // Bowl too narrow
        
        const bowlLow = Math.min(...afterLeftLip.map(q => q.low));
        const depth = (leftLip.price - bowlLow) / leftLip.price;
        
        if (depth > 0.35 || depth < 0.12) return { isCupAndHandle: false }; // Too deep or too shallow

        // Check handle (right side)
        const currentClose = quotes[n - 1].close;
        
        // Handle must be in the upper half of the cup
        const midPoint = bowlLow + ((leftLip.price - bowlLow) / 2);
        if (currentClose < midPoint) return { isCupAndHandle: false };
        
        // Current price must be near the lip (pivot)
        const distToPivot = (leftLip.price - currentClose) / currentClose;
        if (distToPivot <= 0.05 && distToPivot >= -0.02) {
            return {
                isCupAndHandle: true,
                pivot: leftLip.price,
                depth
            };
        }
        
        return { isCupAndHandle: false };
    }

    /**
     * Detect Ascending Triangle (Flat top, higher lows)
     */
    static detectAscendingTriangle(quotes) {
        const n = quotes.length;
        if (n < 40) return { isAscendingTriangle: false };
        
        const last40 = quotes.slice(-40);
        const { highs, lows } = this.identifySwingPoints(last40, 5, 5);
        
        if (highs.length < 2 || lows.length < 2) return { isAscendingTriangle: false };
        
        // Check if highs are relatively flat (within 1.5%)
        const maxHigh = Math.max(...highs.map(h => h.price));
        const minHigh = Math.min(...highs.map(h => h.price));
        if ((maxHigh - minHigh) / maxHigh > 0.015) return { isAscendingTriangle: false };
        
        // Check if lows are strictly ascending
        let isAscending = true;
        for (let i = 1; i < lows.length; i++) {
            if (lows[i].price <= lows[i-1].price) isAscending = false;
        }
        
        if (!isAscending) return { isAscendingTriangle: false };
        
        const currentClose = quotes[n - 1].close;
        const dist = (maxHigh - currentClose) / currentClose;
        
        if (dist <= 0.03 && dist >= -0.01) {
            return {
                isAscendingTriangle: true,
                pivot: maxHigh
            };
        }
        
        return { isAscendingTriangle: false };
    }

    /**
     * Detect Higher-High Higher-Low (HH-HL) trend structure.
     * Confirms a stock is in a structural uptrend by verifying
     * that recent swing highs and swing lows are ascending.
     * @param {Array<Object>} quotes [{date, open, high, low, close}]
     * @returns {Object} { isHHHL, swingHighs, swingLows, trendStrength }
     */
    static detectHigherHighHigherLow(quotes) {
        const n = quotes.length;
        if (n < 60) return { isHHHL: false };
        
        const last60 = quotes.slice(-60);
        const { highs, lows } = this.identifySwingPoints(last60, 5, 5);
        
        if (highs.length < 3 || lows.length < 3) return { isHHHL: false };
        
        // Check last 3 swing highs are ascending
        const recentHighs = highs.slice(-3);
        let highsAscending = true;
        for (let i = 1; i < recentHighs.length; i++) {
            if (recentHighs[i].price <= recentHighs[i-1].price) {
                highsAscending = false;
                break;
            }
        }
        
        // Check last 3 swing lows are ascending
        const recentLows = lows.slice(-3);
        let lowsAscending = true;
        for (let i = 1; i < recentLows.length; i++) {
            if (recentLows[i].price <= recentLows[i-1].price) {
                lowsAscending = false;
                break;
            }
        }
        
        const isHHHL = highsAscending && lowsAscending;
        
        // Trend strength: how consistent is the progression?
        let trendStrength = 0;
        if (highsAscending) trendStrength += 50;
        if (lowsAscending) trendStrength += 50;
        
        return {
            isHHHL,
            swingHighs: recentHighs,
            swingLows: recentLows,
            trendStrength,
            pivot: isHHHL ? recentHighs[recentHighs.length - 1].price : null
        };
    }

    /**
     * Identify clustered Support and Resistance zones
     */
    static identifySupportResistance(quotes) {
        const { highs, lows } = this.identifySwingPoints(quotes, 10, 10);
        
        const clusterPoints = (points, threshold = 0.02) => {
            const clusters = [];
            let sorted = [...points].sort((a, b) => b.price - a.price);
            
            while (sorted.length > 0) {
                const base = sorted[0];
                const cluster = sorted.filter(p => Math.abs(p.price - base.price) / base.price <= threshold);
                clusters.push({
                    price: cluster.reduce((sum, p) => sum + p.price, 0) / cluster.length,
                    strength: cluster.length,
                    points: cluster
                });
                sorted = sorted.filter(p => Math.abs(p.price - base.price) / base.price > threshold);
            }
            return clusters.sort((a, b) => b.strength - a.strength);
        };

        return {
            resistanceZones: clusterPoints(highs).filter(c => c.strength >= 2),
            supportZones: clusterPoints(lows).filter(c => c.strength >= 2)
        };
    }
}
