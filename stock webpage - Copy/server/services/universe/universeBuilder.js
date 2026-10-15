import axios from 'axios';
import zlib from 'zlib';
import csv from 'csv-parser';
import { Readable } from 'stream';

/**
 * Universe Builder
 * Fetches exchange master files and builds the daily security universe,
 * restricting to NSE/BSE Equities and ETFs ONLY.
 * 
 * ROOT CAUSE OF PREVIOUS FAILURE:
 * Upstox CSVs classify bonds, government securities, debentures, and SDLs
 * under instrument_type='EQUITY' with series=''. The previous filter trusted
 * these fields blindly. This version uses aggressive pattern matching on
 * symbol and name to reject non-equity instruments.
 */
export class UniverseBuilder {
    constructor() {
        this.allowedExchanges = ['NSE', 'BSE'];
        this.sectorMap = new Map();
    }

    /**
     * Fetches sector and industry classifications from NSE Nifty 500 list
     */
    async fetchSectorMapping() {
        try {
            console.log('[UniverseBuilder] Fetching sector mapping from NSE Nifty 500 list...');
            const res = await axios.get('https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv', {
                timeout: 5000,
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            });
            const lines = res.data.split('\n');
            const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
            
            const symIdx = headers.findIndex(h => h === 'Symbol');
            const secIdx = headers.findIndex(h => h.includes('Macro-Economic Sector') || h === 'Sector');
            const indIdx = headers.findIndex(h => h === 'Industry');

            if (symIdx === -1 || secIdx === -1 || indIdx === -1) {
                console.warn('[UniverseBuilder] Sector mapping CSV headers missing or changed.');
                return;
            }

            for (let i = 1; i < lines.length; i++) {
                if (!lines[i].trim()) continue;
                // Basic CSV parse (assuming no commas inside quotes for symbol/sector/industry)
                const parts = lines[i].split(',');
                if (parts.length > indIdx) {
                    const symbol = parts[symIdx].trim().replace(/"/g, '');
                    const sector = parts[secIdx].trim().replace(/"/g, '');
                    const industry = parts[indIdx].trim().replace(/"/g, '');
                    this.sectorMap.set(symbol, { sector, industry });
                }
            }
            console.log(`[UniverseBuilder] Successfully mapped sectors for ${this.sectorMap.size} symbols.`);
        } catch (e) {
            console.warn(`[UniverseBuilder] Failed to fetch sector mapping: ${e.message}`);
        }
    }

    /**
     * Determine if an instrument is a genuine equity stock or ETF.
     * Returns { allowed: boolean, is_etf: boolean, reject_reason: string|null }
     */
    classifyInstrument(d) {
        const type = d.instrument_type || '';
        const name = (d.name || '').toUpperCase();
        const symbol = (d.tradingsymbol || '').toUpperCase();

        // ── Step 1: Must be EQUITY type (Upstox labels everything as EQUITY) ──
        if (type !== 'EQUITY') {
            return { allowed: false, is_etf: false, reason: `type=${type}` };
        }

        // ── Step 2: ETF Detection ──
        const isEtf = name.includes('ETF') || name.includes('BEES') || symbol.includes('BEES');

        // ── Step 3: REJECT patterns (applied BEFORE allowing anything) ──

        // 3a. Name contains yield percentage (e.g. "IRFC-7.75%-15-4-33-PVT")
        if (/%/.test(name)) {
            return { allowed: false, is_etf: false, reason: 'yield_pct_in_name' };
        }

        // 3b. Name contains bond/debt keywords
        const debtKeywords = /\b(BOND|NCD|DEBENTURE|DEBT|TBILL|T-BILL|GOVT|GOI|SDL|SGS|GSEC|G-SEC|SOVEREIGN|TREASURY|TAX.?FREE|TAXFREE|PERPETUAL)\b/;
        if (debtKeywords.test(name)) {
            return { allowed: false, is_etf: false, reason: 'debt_keyword_in_name' };
        }

        // 3c. Name ends with -PVT, -PTC, -PPD (private placement markers)
        if (/-(PVT|PTC|PPD|PVTPLC)$/i.test(name) || /-(PVT|PTC|PPD)$/i.test(symbol)) {
            return { allowed: false, is_etf: false, reason: 'private_placement' };
        }

        // 3d. Name looks like a dated instrument: "COMPANY-DATE-DATE-DATE-TYPE"
        // e.g. "EEL-27-01-27-PVT", "PCPL-17-4-28-PVT"
        if (/\d{1,2}-\d{1,2}-\d{2,4}/.test(name)) {
            return { allowed: false, is_etf: false, reason: 'dated_instrument' };
        }

        // 3e. Symbol starts with digits (bonds: 775IRFC33, 182D110626, 749RJ35)
        // Real stock symbols ALWAYS start with a letter in India
        if (/^\d/.test(symbol)) {
            return { allowed: false, is_etf: false, reason: 'symbol_starts_with_digit' };
        }

        // 3f. Symbol matches government security pattern: GS followed by date
        if (/^(GS|SG)\d/.test(symbol)) {
            return { allowed: false, is_etf: false, reason: 'govt_security_symbol' };
        }

        // 3g. Symbol contains ZC (zero coupon) marker
        if (/ZC\d{2}$/.test(symbol) || symbol.includes('ZC2')) {
            return { allowed: false, is_etf: false, reason: 'zero_coupon' };
        }

        // 3h. Symbol matches SDL pattern (State Development Loans)
        if (/^\d+[A-Z]{2}\d{2}[A-Z]?$/.test(symbol)) {
            return { allowed: false, is_etf: false, reason: 'sdl_pattern' };
        }

        // 3i. Symbol has "RESET RATE" or "RR" prefix patterns (floating rate bonds)
        if (/^RR[A-Z]/.test(symbol) && /RESET/i.test(name)) {
            return { allowed: false, is_etf: false, reason: 'reset_rate_bond' };
        }

        // 3j. Name contains "MIBOR" or "LIBOR" (floating rate references)
        if (/MIBOR|LIBOR|SOFR/i.test(name)) {
            return { allowed: false, is_etf: false, reason: 'floating_rate_reference' };
        }

        // 3k. Symbol ends with numbers that look like maturity dates (e.g. PFCLZC26, PCPL28)
        // But be careful: legitimate stocks like "M&M" or "3MINDIA" exist
        // Only reject if symbol has mixed alpha+digit pattern typical of bonds
        if (/^[A-Z]+\d{4,}$/.test(symbol)) {
            return { allowed: false, is_etf: false, reason: 'symbol_with_long_date_suffix' };
        }

        // ── Step 4: If we get here, it's a genuine equity or ETF ──
        return { allowed: true, is_etf: isEtf, reason: null };
    }

    /**
     * Parse Upstox CSV and filter for allowed instruments
     */
    async fetchExchangeMaster(exchange) {
        console.log(`[UniverseBuilder] Fetching master for ${exchange}...`);
        const res = await axios.get(`https://assets.upstox.com/market-quote/instruments/exchange/${exchange}.csv.gz`, {
            responseType: 'arraybuffer'
        });

        const unzipped = zlib.gunzipSync(res.data);
        const stream = Readable.from(unzipped);

        const results = [];
        let rejected = 0;
        
        return new Promise((resolve, reject) => {
            stream.pipe(csv()).on('data', (d) => {
                const classification = this.classifyInstrument(d);

                if (classification.allowed) {
                    results.push({
                        instrument_id: d.instrument_key,
                        symbol: d.tradingsymbol,
                        company_name: d.name,
                        exchange: d.exchange,
                        instrument_type: classification.is_etf ? 'ETF' : 'EQUITY',
                        series: d.series || null,
                        isin: d.isin || null,
                        is_etf: classification.is_etf,
                        is_equity: !classification.is_etf,
                        search_enabled: true,
                        paper_trade_enabled: true,
                        doc_enabled: !classification.is_etf,
                        listing_date: null, // To be populated by corporate actions or NSE scraper
                        delisting_date: null,
                        is_active: true,
                        sector: this.sectorMap.get(d.tradingsymbol)?.sector || null,
                        industry: this.sectorMap.get(d.tradingsymbol)?.industry || null
                    });
                } else {
                    rejected++;
                }
            }).on('end', () => {
                console.log(`[UniverseBuilder] ${exchange}: Allowed ${results.length}, Rejected ${rejected}`);
                resolve(results);
            }).on('error', reject);
        });
    }

    async buildDailyUniverse() {
        await this.fetchSectorMapping();
        
        let fullUniverse = [];
        for (const exch of this.allowedExchanges) {
            const data = await this.fetchExchangeMaster(exch);
            fullUniverse = fullUniverse.concat(data);
        }

        // Deduplicate by symbol to avoid Postgres batch upsert crashes
        const uniqueSymbols = new Map();
        for (const item of fullUniverse) {
            uniqueSymbols.set(item.symbol, item);
        }
        fullUniverse = Array.from(uniqueSymbols.values());
        
        console.log(`[UniverseBuilder] Total universe size: ${fullUniverse.length} instruments (after dedup).`);
        return fullUniverse;
    }
}
