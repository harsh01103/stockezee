export class DataQualityWorker {
    /**
     * Validates a batch of OHLCV records.
     * @param {Array} records - Array of OHLCV objects for a single symbol, sorted by date ascending.
     * @returns {Object} { validRecords: Array, anomalies: Array }
     */
    static validateBatch(records) {
        const validRecords = [];
        const anomalies = [];
        const seenDates = new Set();

        for (let i = 0; i < records.length; i++) {
            const record = records[i];
            const prevRecord = i > 0 ? records[i - 1] : null;

            let isAnomaly = false;
            let anomalyReasons = [];

            // 1. Duplicate Check
            if (seenDates.has(record.date)) {
                isAnomaly = true;
                anomalyReasons.push('Duplicate Date');
            }
            seenDates.add(record.date);

            // 2. Impossible OHLC Check
            if (
                record.high < record.low ||
                record.high < record.close ||
                record.high < record.open ||
                record.low > record.close ||
                record.low > record.open ||
                record.volume < 0
            ) {
                isAnomaly = true;
                anomalyReasons.push('Impossible OHLCV values');
            }

            // 3. Missing Candles / Gaps
            // (In a full implementation, we would check against a trading calendar, skipping weekends/holidays)
            // For now, we note if the date gap is unusually large (> 7 days) which suggests missing data
            if (prevRecord) {
                const prevDate = new Date(prevRecord.date);
                const currDate = new Date(record.date);
                const diffTime = Math.abs(currDate - prevDate);
                const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)); 
                
                if (diffDays > 10) {
                    // Not necessarily an anomaly that invalidates the record, but a warning for the dataset
                    anomalyReasons.push(`Gap of ${diffDays} days`);
                }

                // 4. Split Anomalies
                // A sudden drop of 33% (3:2), 50% (2:1), etc., without a corporate action flag
                // We use a simple 30% drop threshold as a heuristic for a potential unadjusted split
                const priceDropPct = (prevRecord.close - record.open) / prevRecord.close;
                if (priceDropPct > 0.30) {
                    anomalyReasons.push(`Potential Unadjusted Split (Drop of ${(priceDropPct*100).toFixed(1)}%)`);
                }
            }

            if (isAnomaly) {
                anomalies.push({ record, reasons: anomalyReasons });
            } else {
                // If it only has non-fatal warnings (like gap or split warning), we can still keep it but maybe log it
                if (anomalyReasons.length > 0) {
                    // Log warnings
                    // console.warn(`[DataQuality] Warning for ${record.symbol} on ${record.date}:`, anomalyReasons);
                }
                validRecords.push(record);
            }
        }

        return { validRecords, anomalies };
    }
}
