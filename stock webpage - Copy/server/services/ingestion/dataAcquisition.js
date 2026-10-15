import { Queue, Worker } from 'bullmq';
import { connection } from '../queue/connection.js';
import { SecurityMaster } from '../universe/securityMaster.js';
import { DataAcquisitionManager } from './providerInterface.js';
import { YahooFinanceProvider } from './providers/yahooFinanceProvider.js';
import { NseBhavcopyProvider } from './providers/nseBhavcopyProvider.js';
import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config({ path: path.join(__dirname, '../../../.env') });

const supabaseUrl = process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE;
const supabase = createClient(supabaseUrl, supabaseKey);

const acquisitionManager = new DataAcquisitionManager();
acquisitionManager.registerProvider(new NseBhavcopyProvider());
acquisitionManager.registerProvider(new YahooFinanceProvider());

// Queue for scheduling EOD data downloads
export const eodDataQueue = new Queue('EOD_Data_Queue', { connection });

// Worker that processes each symbol's EOD download
const eodDataWorker = new Worker('EOD_Data_Queue', async (job) => {
    const { symbol } = job.data;
    console.log(`[EOD Worker] Processing data for ${symbol}`);
    
    try {
        // Calculate 5 years ago for deep research (residual momentum requires ~36 months minimum)
        const endDate = new Date();
        const startDate = new Date();
        startDate.setFullYear(endDate.getFullYear() - 5);
        
        // Jitter to prevent rate limiting (500ms to 2000ms)
        await new Promise(resolve => setTimeout(resolve, 500 + Math.random() * 1500));
        
        // Fetch 5 years of daily data using the provider abstraction
        const result = await acquisitionManager.fetchHistoricalOHLCV(symbol, startDate, endDate);
        
        if (!result || result.length === 0) {
            console.warn(`[EOD Worker] No data found for ${symbol}`);
            return;
        }

        console.log(`[EOD Worker] Fetched ${result.length} days of data for ${symbol}`);
        
        // Map to DB schema
        const mappedData = result.map(q => ({
            symbol: q.symbol,
            date: q.date,
            open: q.open,
            high: q.high,
            low: q.low,
            close: q.close,
            volume: q.volume,
            traded_value: q.traded_value,
            updated_at: new Date().toISOString()
        }));

        // Upsert into daily_ohlcv
        const { error } = await supabase
            .from('daily_ohlcv')
            .upsert(mappedData, { onConflict: 'symbol,date' });
            
        if (error) {
            console.error(`[EOD Worker] Error inserting data for ${symbol}:`, error);
            throw error;
        }

        console.log(`[EOD Worker] Successfully saved data for ${symbol}`);
    } catch (err) {
        console.error(`[EOD Worker] Failed to process ${symbol}:`, err.message);
        throw err; // BullMQ will retry based on job settings
    }
}, { 
    connection,
    concurrency: 5 // Process 5 symbols concurrently
});

eodDataWorker.on('completed', (job) => {
    // console.log(`[EOD Worker] Job ${job.id} has completed!`);
});

eodDataWorker.on('failed', (job, err) => {
    console.error(`[EOD Worker] Job ${job.id} has failed with ${err.message}`);
});

/**
 * Trigger EOD download for all active symbols
 */
export async function queueEODDownloads() {
    console.log('[EOD Data Queue] Fetching universe to schedule downloads...');
    try {
        const universe = await SecurityMaster.getActiveUniverse();
        console.log(`[EOD Data Queue] Queuing ${universe.length} symbols...`);
        
        const jobs = universe.map(stock => ({
            name: `EOD_${stock.symbol}`,
            data: { symbol: stock.symbol },
            opts: {
                attempts: 3,
                backoff: {
                    type: 'exponential',
                    delay: 5000,
                },
                removeOnComplete: true,
                removeOnFail: false
            }
        }));
        
        await eodDataQueue.addBulk(jobs);
        console.log('[EOD Data Queue] All jobs queued successfully.');
    } catch (err) {
        console.error('[EOD Data Queue] Error queuing jobs:', err);
    }
}
