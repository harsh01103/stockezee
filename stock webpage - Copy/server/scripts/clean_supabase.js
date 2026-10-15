import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import { UniverseBuilder } from '../services/universe/universeBuilder.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config({ path: path.resolve(__dirname, '../.env') });

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE;

if (!SUPABASE_URL || !SUPABASE_KEY) {
    console.error('Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE in server/.env');
    process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

async function run() {
    console.log('=== PHASE 3: CLEAN EXISTING DATA ===\n');

    // ── Step 1: Count existing records ──
    const { count: docsBefore } = await supabase
        .from('company_document_features')
        .select('*', { count: 'exact', head: true });
    console.log(`[Before] company_document_features rows: ${docsBefore ?? 'table not found'}`);

    const { count: secBefore } = await supabase
        .from('security_master')
        .select('*', { count: 'exact', head: true });
    console.log(`[Before] security_master rows: ${secBefore ?? 'table not found'}`);

    // ── Step 2: Build the clean universe ──
    console.log('\n=== PHASE 4: REBUILD SECURITY MASTER ===\n');
    const builder = new UniverseBuilder();
    const universe = await builder.buildDailyUniverse();

    const validSymbols = new Set(universe.map(u => u.symbol));
    console.log(`Clean universe size: ${universe.length}`);
    console.log(`Unique symbols: ${validSymbols.size}`);

    // ── Step 3: Delete invalid company_document_features ──
    if (docsBefore && docsBefore > 0) {
        console.log('\nCleaning company_document_features...');
        
        // Fetch all existing doc symbols
        const { data: existingDocs, error: fetchErr } = await supabase
            .from('company_document_features')
            .select('id, symbol');
        
        if (fetchErr) {
            console.error('Error fetching docs:', fetchErr.message);
        } else if (existingDocs) {
            const invalidDocs = existingDocs.filter(d => !validSymbols.has(d.symbol));
            console.log(`  Found ${invalidDocs.length} invalid documents out of ${existingDocs.length} total.`);
            
            if (invalidDocs.length > 0) {
                // Delete in batches of 500
                const batchSize = 500;
                let deleted = 0;
                for (let i = 0; i < invalidDocs.length; i += batchSize) {
                    const batch = invalidDocs.slice(i, i + batchSize);
                    const ids = batch.map(d => d.id);
                    const { error: delErr } = await supabase
                        .from('company_document_features')
                        .delete()
                        .in('id', ids);
                    
                    if (delErr) {
                        console.error(`  Batch delete error at offset ${i}:`, delErr.message);
                    } else {
                        deleted += batch.length;
                    }
                }
                console.log(`  Deleted ${deleted} invalid document features.`);
            }
        }
    }

    // ── Step 4: Wipe and rebuild security_master ──
    console.log('\nRebuilding security_master...');
    
    // Clear old security_master
    const { error: clearErr } = await supabase
        .from('security_master')
        .delete()
        .neq('instrument_id', '__impossible__'); // delete all rows
    
    if (clearErr) {
        console.error('Error clearing security_master:', clearErr.message);
        // Table might not exist yet - try to proceed
        console.log('Table may not exist yet. Attempting upserts...');
    }

    // Insert in batches of 500
    const batchSize = 500;
    let inserted = 0;
    let errors = 0;
    for (let i = 0; i < universe.length; i += batchSize) {
        const batch = universe.slice(i, i + batchSize).map(u => ({
            instrument_id: u.instrument_id,
            symbol: u.symbol,
            company_name: u.company_name,
            exchange: u.exchange,
            instrument_type: u.instrument_type,
            series: u.series,
            isin: u.isin,
            is_etf: u.is_etf,
            is_equity: u.is_equity,
            search_enabled: u.search_enabled,
            paper_trade_enabled: u.paper_trade_enabled,
            doc_enabled: u.doc_enabled,
            last_updated: new Date().toISOString()
        }));

        const { error: insertErr } = await supabase
            .from('security_master')
            .upsert(batch, { onConflict: 'instrument_id' });

        if (insertErr) {
            console.error(`  Insert batch error at offset ${i}:`, insertErr.message);
            errors++;
        } else {
            inserted += batch.length;
        }
    }
    console.log(`  Inserted/upserted ${inserted} instruments (${errors} batch errors).`);

    // ── Step 5: Final counts ──
    console.log('\n=== FINAL COUNTS ===\n');
    
    const { count: secAfter } = await supabase
        .from('security_master')
        .select('*', { count: 'exact', head: true });
    console.log(`security_master rows: ${secAfter}`);

    const { count: docsAfter } = await supabase
        .from('company_document_features')
        .select('*', { count: 'exact', head: true });
    console.log(`company_document_features rows: ${docsAfter}`);

    const { count: tradesCount } = await supabase
        .from('trades')
        .select('*', { count: 'exact', head: true });
    console.log(`trades rows (PRESERVED): ${tradesCount}`);

    // Stats
    const nse = universe.filter(u => u.exchange.includes('NSE')).length;
    const bse = universe.filter(u => u.exchange.includes('BSE')).length;
    const etfs = universe.filter(u => u.is_etf).length;

    console.log(`\nNSE: ${nse} | BSE: ${bse} | ETFs: ${etfs}`);
    console.log('\n✅ Universe repair complete. Trades preserved. Deployment intact.');
}

run().catch(err => {
    console.error('FATAL ERROR:', err);
    process.exit(1);
});
