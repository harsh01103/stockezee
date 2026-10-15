import { UniverseBuilder } from '../universe/universeBuilder.js';
import { docIntelPipeline } from '../docintel/pipeline.js';
import { fetchExchangeDocuments } from '../docintel/fetchers/exchangeFetcher.js';
import { fetchIRDocuments } from '../docintel/fetchers/investorRelationsFetcher.js';
import { fetchPDFDocuments } from '../docintel/fetchers/pdfFetcher.js';
import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config({ path: path.resolve(__dirname, '../../.env') });

import ws from 'ws';

const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE, {
    auth: { persistSession: false },
    realtime: { transport: ws }
});

export async function runNightlyIngestion() {
    console.log('[NightlyJob] Starting nightly ingestion engine...');

    const startTime = Date.now();

    // 1. Refresh Universe
    const builder = new UniverseBuilder();
    const universe = await builder.buildDailyUniverse();
    
    console.log(`[NightlyJob] Universe refreshed. Total instruments: ${universe.length}`);

    // 2. Find eligible companies for document processing
    const docEligible = universe.filter(u => u.doc_enabled && u.is_equity);
    console.log(`[NightlyJob] Found ${docEligible.length} companies eligible for Document Intelligence.`);

    // 3. Process documents (Real Fetch & Persist)
    let fetchedCount = 0;
    let insertedCount = 0;
    let processedCount = 0;
    let failedCount = 0;

    // Use a smaller batch size to avoid rate limits on real APIs (e.g. Yahoo Finance)
    const batchSize = 10;
    
    for (let i = 0; i < docEligible.length; i += batchSize) {
        const batch = docEligible.slice(i, i + batchSize);
        
        await Promise.all(batch.map(async (company) => {
            try {
                // FETCH REAL DOCUMENTS
                const exchangeDocs = await fetchExchangeDocuments(company.symbol, company.exchange);
                const irDocs = await fetchIRDocuments(company.symbol, company.exchange);
                const pdfDocs = await fetchPDFDocuments(company.symbol, company.exchange);
                
                const allDocs = [...exchangeDocs, ...irDocs, ...pdfDocs];
                fetchedCount += allDocs.length;

                if (allDocs.length > 0) {
                    // PERSIST DOCUMENTS
                    const { data: insertedDocs, error: upsertErr } = await supabase
                        .from('company_documents')
                        .upsert(allDocs, { onConflict: 'hash', ignoreDuplicates: true })
                        .select('id, title, hash');

                    if (upsertErr) {
                        console.error(`[NightlyJob] Upsert error for ${company.symbol}: ${upsertErr.message}`);
                        failedCount++;
                        return; // Skip processing if we can't persist
                    }

                    if (insertedDocs && insertedDocs.length > 0) {
                        insertedCount += insertedDocs.length;
                        
                        // PROCESS & GENERATE FEATURES
                        for (const doc of insertedDocs) {
                            try {
                                await docIntelPipeline.processFiling(doc.id);
                                processedCount++;
                            } catch (procErr) {
                                console.error(`[NightlyJob] Failed to process doc ${doc.id}: ${procErr.message}`);
                                failedCount++;
                            }
                        }
                    }
                }
            } catch (err) {
                console.error(`[NightlyJob] Pipeline failed for ${company.symbol}: ${err.message}`);
                failedCount++;
            }
        }));
        
        // Brief delay between batches to respect rate limits
        if (i + batchSize < docEligible.length) {
            await new Promise(res => setTimeout(res, 2000));
        }
    }

    const duration = ((Date.now() - startTime) / 1000).toFixed(2);
    console.log(`[NightlyJob] Completed in ${duration}s.`);
    console.log(`[NightlyJob] Fetched: ${fetchedCount} | Inserted: ${insertedCount} | Processed: ${processedCount} | Failed: ${failedCount}`);

    return {
        total_listed: universe.length,
        documents_found: fetchedCount,
        documents_inserted: insertedCount,
        documents_processed: processedCount,
        documents_failed: failedCount,
        duration_sec: duration
    };
}

// Allow running manually via CLI
if (process.argv[1] && process.argv[1].endsWith('nightlyJob.js')) {
    runNightlyIngestion().then(console.log).catch(console.error);
}
