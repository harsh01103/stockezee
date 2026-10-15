/**
 * Fundamental Engine
 * Fetches and scores financial health metrics using Yahoo Finance quoteSummary.
 */
import YahooFinance from 'yahoo-finance2';
const yahooFinance = new YahooFinance();

export class FundamentalEngine {
    
    /**
     * Fetch fundamental data from Yahoo Finance and score it.
     * @param {string} symbol 
     * @returns {Object} { score, metrics }
     */
    static async scoreFundamentals(symbol) {
        try {
            // Some NSE symbols need .NS suffix for Yahoo Finance
            const yfSymbol = symbol.endsWith('.NS') || symbol.endsWith('.BO') ? symbol : `${symbol}.NS`;
            
            // Try fetching financialData and defaultKeyStatistics
            const quoteSummary = await yahooFinance.quoteSummary(yfSymbol, {
                modules: ['financialData', 'defaultKeyStatistics']
            }).catch(() => null);

            if (!quoteSummary || !quoteSummary.financialData) {
                // Return neutral score if data unavailable
                return { score: 30, metrics: null, status: 'MISSING' };
            }

            const fd = quoteSummary.financialData;
            const ks = quoteSummary.defaultKeyStatistics || {};

            const metrics = {
                roe: fd.returnOnEquity,
                operatingMargin: fd.operatingMargins,
                profitMargin: fd.profitMargins,
                revenueGrowth: fd.revenueGrowth,
                epsGrowth: fd.earningsGrowth,
                currentRatio: fd.currentRatio,
                debtToEquity: fd.debtToEquity ? fd.debtToEquity / 100 : null, // YF sometimes gives D/E as 150 meaning 1.5
                peRatio: ks.forwardPE || ks.trailingPE || null,
                priceToBook: ks.priceToBook || null
            };

            let score = 50; // Start neutral
            
            // ── PROFITABILITY (Max +20) ──
            if (metrics.roe) {
                if (metrics.roe > 0.20) score += 10;
                else if (metrics.roe > 0.12) score += 5;
                else if (metrics.roe < 0) score -= 15;
            }
            if (metrics.operatingMargin) {
                if (metrics.operatingMargin > 0.15) score += 5;
                else if (metrics.operatingMargin > 0.08) score += 2;
                else if (metrics.operatingMargin < 0) score -= 10;
            }
            if (metrics.profitMargin !== null && metrics.profitMargin !== undefined) {
                if (metrics.profitMargin > 0.05) score += 5;
                else if (metrics.profitMargin < 0) score -= 20; // Heavy penalty for net loss
            }

            // ── GROWTH (Max +15) ──
            if (metrics.revenueGrowth) {
                if (metrics.revenueGrowth > 0.20) score += 10;
                else if (metrics.revenueGrowth > 0.05) score += 5;
                else if (metrics.revenueGrowth < 0) score -= 15;
            }
            if (metrics.epsGrowth !== null && metrics.epsGrowth !== undefined) {
                if (metrics.epsGrowth > 0.10) score += 5;
                else if (metrics.epsGrowth < 0) score -= 15; // Penalty for shrinking earnings
            }

            // ── VALUATION & SOLVENCY (Max +15) ──
            if (metrics.peRatio) {
                if (metrics.peRatio > 0 && metrics.peRatio < 30) score += 5;
                else if (metrics.peRatio > 80) score -= 10; // Absurdly overvalued
            }
            if (metrics.debtToEquity !== null) {
                if (metrics.debtToEquity < 0.5) score += 5;
                else if (metrics.debtToEquity > 1.5) score -= 10;
            }
            if (metrics.currentRatio && metrics.currentRatio > 1.2) score += 5;

            // Cap score between 0 and 100
            score = Math.max(0, Math.min(100, score));

            return {
                score,
                metrics,
                status: 'OK'
            };

        } catch (e) {
            console.warn(`[FundamentalEngine] Failed to fetch fundamentals for ${symbol}: ${e.message}`);
            return { score: 30, metrics: null, status: 'ERROR' };
        }
    }
}
