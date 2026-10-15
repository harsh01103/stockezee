import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';
import { YahooFinanceProvider } from '../providers/yahooFinanceProvider.js';
import { UniverseBuilder } from '../../universe/universeBuilder.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config({ path: path.join(__dirname, '../../../.env') });

const supabaseUrl = process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE;

if (!supabaseUrl || !supabaseKey) {
    console.error('Missing Supabase credentials in .env');
    process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseKey);
const yfProvider = new YahooFinanceProvider();
const STATE_FILE = path.join(__dirname, 'backfill_state.json');

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const randomJitter = (min, max) => Math.floor(Math.random() * (max - min + 1) + min);

async function loadState() {
    if (fs.existsSync(STATE_FILE)) {
        return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    }
    return { completed_symbols: [], failed_symbols: [], last_run: null };
}

async function saveState(state) {
    state.last_run = new Date().toISOString();
    fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

async function runBackfill() {
    console.log('=== Starting Deep Historical Backfill (5Y) ===');
    const state = await loadState();
    console.log(`Loaded state: ${state.completed_symbols.length} already completed.`);

    const universeBuilder = new UniverseBuilder();
    const fullUniverse = await universeBuilder.buildDailyUniverse();
    console.log(`Total Universe Size: ${fullUniverse.length}`);

    const symbolsToProcess = fullUniverse
        .map(u => u.symbol)
        .filter(s => !state.completed_symbols.includes(s));

    console.log(`Remaining to process: ${symbolsToProcess.length}`);

    // Set end date to today, start date to 5 years ago
    const endDate = new Date();
    const startDate = new Date();
    startDate.setFullYear(endDate.getFullYear() - 5);

    let batchCount = 0;

    for (let i = 0; i < symbolsToProcess.length; i++) {
        const symbol = symbolsToProcess[i];
        console.log(`[${i+1}/${symbolsToProcess.length}] Fetching 5Y history for ${symbol}...`);

        let success = false;
        let attempts = 0;
        let data = [];

        while (!success && attempts < 3) {
            attempts++;
            try {
                data = await yfProvider.fetchHistoricalOHLCV(symbol, startDate, endDate);
                success = true;
            } catch (error) {
                console.warn(`Attempt ${attempts} failed for ${symbol}: ${error.message}`);
                if (error.message.includes('429')) {
                    console.log('Rate limit hit. Sleeping for 60 seconds...');
                    await sleep(60000); // 1 minute backoff on 429
                } else if (error.message.includes('No data')) {
                    console.log(`No data for ${symbol}. Probably recently listed or invalid on YF.`);
                    break; // Don't retry if it just doesn't exist
                } else {
                    await sleep(5000);
                }
            }
        }

        if (success && data.length > 0) {
            // Upsert into Supabase in chunks of 1000 rows to avoid payload limits
            const chunkSize = 1000;
            let dbSuccess = true;
            
            for (let j = 0; j < data.length; j += chunkSize) {
                const chunk = data.slice(j, j + chunkSize);
                const { error } = await supabase
                    .from('daily_ohlcv')
                    .upsert(chunk, { onConflict: 'symbol, date' });
                
                if (error) {
                    console.error(`DB Insert failed for ${symbol}:`, error);
                    dbSuccess = false;
                    break;
                }
            }

            if (dbSuccess) {
                console.log(`✔ Saved ${data.length} records for ${symbol}`);
                state.completed_symbols.push(symbol);
                batchCount++;
            } else {
                state.failed_symbols.push(symbol);
            }
        } else {
            console.log(`✖ Skipped/Failed ${symbol}`);
            state.failed_symbols.push(symbol);
            batchCount++; // Still count it so we save state
        }

        // Save state every 10 symbols
        if (batchCount >= 10) {
            await saveState(state);
            batchCount = 0;
        }

        // Jitter delay between 1.5 and 3.5 seconds to avoid bans
        const delay = randomJitter(1500, 3500);
        await sleep(delay);
    }

    await saveState(state);
    console.log('=== Backfill Complete ===');
}

runBackfill().catch(console.error);
