import axios from 'axios';
import yauzl from 'yauzl';
import csv from 'csv-parser';
import { DataProvider } from '../providerInterface.js';

export class NseBhavcopyProvider extends DataProvider {
    constructor() {
        super('NseBhavcopy');
    }

    /**
     * Converts a Date to the NSE Bhavcopy date format (e.g., cm01SEP2023bhav.csv.zip)
     */
    getBhavcopyUrl(date) {
        const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
        const dd = String(date.getDate()).padStart(2, '0');
        const mmm = months[date.getMonth()];
        const yyyy = date.getFullYear();
        // Modern URL structure (often changes, using standard historical archive format)
        return `https://nsearchives.nseindia.com/content/historical/EQUITIES/${yyyy}/${mmm}/cm${dd}${mmm}${yyyy}bhav.csv.zip`;
    }

    /**
     * Fetches Bhavcopy for a specific date and parses all symbols.
     * Note: In production, we'd cache this per-day so we only download the zip once
     * even if fetchHistoricalOHLCV is called for 7,500 symbols individually.
     */
    async fetchBhavcopyForDate(date) {
        const url = this.getBhavcopyUrl(date);
        
        try {
            const res = await axios.get(url, {
                responseType: 'arraybuffer',
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': '*/*'
                },
                timeout: 10000
            });

            return new Promise((resolve, reject) => {
                const results = new Map();
                yauzl.fromBuffer(res.data, { lazyEntries: true }, (err, zipfile) => {
                    if (err) return reject(err);
                    
                    zipfile.readEntry();
                    zipfile.on('entry', (entry) => {
                        if (/\/$/.test(entry.fileName)) {
                            zipfile.readEntry(); // Directory
                        } else if (entry.fileName.endsWith('.csv')) {
                            zipfile.openReadStream(entry, (err, readStream) => {
                                if (err) return reject(err);
                                
                                readStream.pipe(csv())
                                    .on('data', (row) => {
                                        if (row.SERIES === 'EQ') { // Only Equity
                                            results.set(row.SYMBOL, {
                                                symbol: row.SYMBOL,
                                                date: date.toISOString().split('T')[0],
                                                open: parseFloat(row.OPEN),
                                                high: parseFloat(row.HIGH),
                                                low: parseFloat(row.LOW),
                                                close: parseFloat(row.CLOSE),
                                                volume: parseInt(row.TOTTRDQTY, 10),
                                                traded_value: parseFloat(row.TOTTRDVAL),
                                                source: this.name,
                                                retrieved_at: new Date().toISOString(),
                                                confidence: 1.0 // High confidence for official exchange data
                                            });
                                        }
                                    })
                                    .on('end', () => {
                                        resolve(results);
                                    });
                            });
                        } else {
                            zipfile.readEntry();
                        }
                    });
                });
            });
        } catch (e) {
            if (e.response && e.response.status === 404) {
                // Not a trading day or not available
                return new Map();
            }
            throw new Error(`Bhavcopy fetch failed for ${date.toISOString()}: ${e.message}`);
        }
    }

    /**
     * Implements DataProvider interface.
     * Note: Since Bhavcopy is point-in-time cross-sectional, we have to download the ZIP 
     * for every single day in the date range. This is great for daily EOD updates, but 
     * terrible for fetching 5 years of history for a single stock.
     */
    async fetchHistoricalOHLCV(symbol, startDate, endDate) {
        // Warning: This is just a stub for fetching a single symbol from Bhavcopies over a range.
        // In the real system, you'd download the Bhavcopy ONCE per day, save it to DB, 
        // and query the DB. We return empty here to signal it should be used for EOD, not 5Y history.
        
        // For demonstration, if the range is just 1 day, we fetch it:
        const diffTime = Math.abs(endDate - startDate);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)); 
        
        if (diffDays <= 3) {
            let ohlcv = [];
            for (let d = new Date(startDate); d <= endDate; d.setDate(d.getDate() + 1)) {
                // skip weekends roughly
                if (d.getDay() === 0 || d.getDay() === 6) continue;
                
                try {
                    const dataMap = await this.fetchBhavcopyForDate(d);
                    const row = dataMap.get(symbol);
                    if (row) ohlcv.push(row);
                } catch (e) {
                    console.warn(`[NseBhavcopyProvider] Failed on ${d.toISOString()}: ${e.message}`);
                }
            }
            return ohlcv;
        }

        // For long histories, throw error to trigger YahooFinance fallback
        throw new Error('NseBhavcopyProvider is optimized for daily EOD cross-sectional updates, not multi-year individual symbol queries. Use YahooFinance for history.');
    }
}
