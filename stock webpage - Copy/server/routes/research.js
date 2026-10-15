import express from 'express';
import { createClient } from '@supabase/supabase-js';
import { startNightlyPipeline, ingestionQueue, computeQueue, deepAnalysisQueue, fundamentalQueue, sentimentQueue, fusionQueue } from '../services/compute/pipelineOrchestrator.js';
import { connection } from '../services/queue/connection.js';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import crypto from 'crypto';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config({ path: path.join(__dirname, '../.env') });

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE;
const supabase = createClient(supabaseUrl, supabaseKey);

const router = express.Router();

/**
 * GET /api/research/regime
 * Returns the latest market regime analysis.
 */
router.get('/regime', async (req, res) => {
    try {
        const { data, error } = await supabase
            .from('market_regime')
            .select('*')
            .order('date', { ascending: false })
            .limit(1)
            .single();

        if (error) throw error;
        res.json({ success: true, regime: data });
    } catch (err) {
        res.json({ success: true, regime: null });
    }
});

/**
 * GET /api/research/watchlist
 * Returns high-conviction trade plans for the given horizon.
 * @query horizon (e.g., 'next_session', 'next_week')
 */
router.get('/watchlist', async (req, res) => {
    try {
        const { horizon } = req.query;
        // Find latest run ID
        const { data: latestRun } = await supabase
            .from('analysis_runs')
            .select('id')
            .order('start_time', { ascending: false })
            .limit(1)
            .single();

        let query = supabase
            .from('trade_plans')
            .select('*')
            .eq('run_id', latestRun ? latestRun.id : null)
            .order('opportunity_score', { ascending: false })
            .limit(20);

        if (horizon === 'next_session') {
            query = query.eq('trade_readiness', 'READY');
        } else if (horizon === 'next_week') {
            query = query.eq('trade_readiness', 'DEVELOPING');
        } else {
            query = query.in('trade_readiness', ['READY', 'DEVELOPING', 'NEAR_TRIGGER']);
        }

        const { data, error } = await query;
        if (error) throw error;
        
        const uniqueData = [];
        const seen = new Set();
        for (const item of (data || [])) {
            if (!seen.has(item.symbol)) {
                seen.add(item.symbol);
                uniqueData.push(item);
            }
        }
        
        res.json({ success: true, watchlist: uniqueData });
    } catch (err) {
        res.json({ success: true, watchlist: [] });
    }
});

/**
 * GET /api/research/stock/:symbol
 * Full deep analysis and chart annotations for a specific stock.
 */
router.get('/stock/:symbol', async (req, res) => {
    try {
        const { symbol } = req.params;
        const normalizedSymbol = symbol.toUpperCase();

        const [planRes, annotationsRes, ohlcvRes] = await Promise.all([
            supabase.from('trade_plans').select('*').eq('symbol', normalizedSymbol).order('date', { ascending: false }).limit(1).single(),
            supabase.from('chart_annotations').select('annotations').eq('symbol', normalizedSymbol).order('date', { ascending: false }).limit(1).single(),
            supabase.from('daily_ohlcv').select('date, open, high, low, close, volume').eq('symbol', normalizedSymbol).order('date', { ascending: true }).limit(250)
        ]);

        res.json({
            success: true,
            plan: planRes.data || null,
            annotations: annotationsRes.data?.annotations || null,
            ohlcv: ohlcvRes.data || null
        });
    } catch (err) {
        res.status(500).json({ success: false, error: err.message });
    }
});

/**
 * POST /api/research/run
 * Triggers the full nightly research pipeline.
 */
router.post('/run', async (req, res) => {
    try {
        const runId = crypto.randomUUID();
        await startNightlyPipeline(runId);
        res.json({ success: true, runId, message: 'Pipeline started.' });
    } catch (err) {
        res.status(500).json({ success: false, error: err.message });
    }
});

/**
 * GET /api/research/status
 * Returns the latest pipeline run status.
 */
router.get('/status', async (req, res) => {
    try {
        const { data, error } = await supabase
            .from('analysis_runs')
            .select('*')
            .order('start_time', { ascending: false })
            .limit(1)
            .single();
        
        if (error) throw error;

        // Calculate progress dynamically based on Ingestion queue
        let processedSymbols = 0;
        
        if (data && data.status === 'RUNNING' && data.current_stage !== 'UNIVERSE') {
            // Read accurate processed count from Redis
            const rawCount = await connection.get(`run:${data.id}:processed_symbols`);
            processedSymbols = rawCount ? parseInt(rawCount, 10) : 0;
            
            if (processedSymbols >= (data.universe_size || 9000)) {
                processedSymbols = data.universe_size;
                
                // If Ingestion is done, check if all downstream queues are empty
                const computeCounts = await computeQueue.getJobCounts('active', 'waiting', 'completed');
                const deepCounts = await deepAnalysisQueue.getJobCounts('active', 'waiting', 'completed');
                const fundCounts = await fundamentalQueue.getJobCounts('active', 'waiting', 'completed');
                const sentimentCounts = await sentimentQueue.getJobCounts('active', 'waiting', 'completed');
                const fusionCounts = await fusionQueue.getJobCounts('active', 'waiting', 'completed');
                
                const downstreamActive = computeCounts.active + computeCounts.waiting + 
                                         deepCounts.active + deepCounts.waiting + 
                                         fundCounts.active + fundCounts.waiting +
                                         sentimentCounts.active + sentimentCounts.waiting +
                                         fusionCounts.active + fusionCounts.waiting;

                // If nothing is left in the pipeline, mark it as COMPLETED
                if (downstreamActive === 0) {
                    await supabase.from('analysis_runs').update({
                        status: 'COMPLETED',
                        current_stage: 'DONE',
                        end_time: new Date().toISOString()
                    }).eq('id', data.id);
                    data.status = 'COMPLETED';
                    data.current_stage = 'DONE';
                } else {
                    // Dynamically infer current stage by tracking the "tail" of the pipeline.
                    // Because Ingestion is done, queues will only ever drain.
                    if (computeCounts.active + computeCounts.waiting > 0) {
                        data.current_stage = 'COMPUTE';
                    } else if (deepCounts.active + deepCounts.waiting > 0) {
                        data.current_stage = 'DEEP_ANALYSIS';
                    } else if (fundCounts.active + fundCounts.waiting > 0) {
                        data.current_stage = 'FUNDAMENTALS';
                    } else if (sentimentCounts.active + sentimentCounts.waiting > 0) {
                        data.current_stage = 'SENTIMENT';
                    } else if (fusionCounts.active + fusionCounts.waiting > 0) {
                        data.current_stage = 'FUSION';
                    } else {
                        data.current_stage = 'FUSION'; // Edge case fallback before downstreamActive triggers
                    }
                }
            }
        }

        res.json({ success: true, run: { ...data, processed_symbols: processedSymbols } });
    } catch (err) {
        res.json({ success: true, run: null });
    }
});

export default router;

