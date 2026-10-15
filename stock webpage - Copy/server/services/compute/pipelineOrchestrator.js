import { Queue, Worker } from 'bullmq';
import { connection } from '../queue/connection.js';
import { UniverseBuilder } from '../universe/universeBuilder.js';
import { SecurityMaster } from '../universe/securityMaster.js';
import { DataAcquisitionManager } from '../ingestion/providerInterface.js';
import { YahooFinanceProvider } from '../ingestion/providers/yahooFinanceProvider.js';
import { FeatureEngine } from './featureEngine.js';
import { TechnicalEngine } from './technicalEngine.js';
import { PatternEngine } from './patternEngine.js';
import { FusionEngine } from './fusionEngine.js';
import { FundamentalEngine } from './fundamentalEngine.js';
import { SectorRotationEngine } from './sectorRotationEngine.js';
import { docIntelPipeline } from '../docintel/pipeline.js';
import { regimeEngine } from '../regime/regimeEngine.js';
import YahooFinance from 'yahoo-finance2';
const yahooFinance = new YahooFinance();
import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config({ path: path.resolve(__dirname, '../../.env') });

const supabase = createClient(
    process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL,
    process.env.SUPABASE_SERVICE_ROLE
);

const acquisitionManager = new DataAcquisitionManager();
acquisitionManager.registerProvider(new YahooFinanceProvider());

// Define queues for the 6-stage pipeline
export const universeQueue = new Queue('UniverseQueue', { connection });
export const ingestionQueue = new Queue('IngestionQueue', { connection });
export const computeQueue = new Queue('ComputeQueue', { connection });
export const deepAnalysisQueue = new Queue('DeepAnalysisQueue', { connection });
export const fundamentalQueue = new Queue('FundamentalQueue', { connection });
export const sentimentQueue = new Queue('SentimentQueue', { connection });
export const fusionQueue = new Queue('FusionQueue', { connection });

/**
 * Triggers the full nightly analysis pipeline.
 */
export async function startNightlyPipeline(runId) {
    console.log(`[Pipeline] Starting nightly run: ${runId}`);
    console.log(`[Pipeline] Cleaning old queues...`);

    const queues = [universeQueue, ingestionQueue, computeQueue, deepAnalysisQueue, fundamentalQueue, sentimentQueue, fusionQueue];
    for (const q of queues) {
        try {
            await q.drain(true);
            await q.clean(0, 100000, 'completed');
            await q.clean(0, 100000, 'failed');
            await q.clean(0, 100000, 'wait');
            await q.clean(0, 100000, 'active');
        } catch (e) {
            console.warn(`[Pipeline] Could not fully clean queue: ${e.message}`);
        }
    }

    await supabase.from('analysis_runs').upsert({
        id: runId,
        status: 'RUNNING',
        current_stage: 'UNIVERSE',
        start_time: new Date().toISOString()
    }, { onConflict: 'id' });

    await universeQueue.add('build_universe', { runId }, {
        removeOnComplete: true,
        attempts: 3
    });
}

// ─────────────────────────────────────────────────────────
// STAGE 1: UNIVERSE — Build active universe from Upstox
// ─────────────────────────────────────────────────────────
const universeWorker = new Worker('UniverseQueue', async (job) => {
    const { runId } = job.data;
    console.log(`[UniverseWorker] Building universe for run ${runId}...`);

    const builder = new UniverseBuilder();
    const fullUniverse = await builder.buildDailyUniverse();

    const insertChunkSize = 1000;
    for (let i = 0; i < fullUniverse.length; i += insertChunkSize) {
        const chunk = fullUniverse.slice(i, i + insertChunkSize);
        try {
            await SecurityMaster.upsertSymbolsBatch(chunk);
        } catch (e) {
            console.error('[UniverseWorker] Batch upsert failed:', e);
        }
    }

    const activeRecords = await SecurityMaster.getActiveUniverse();
    const activeSymbols = activeRecords.map(r => r.symbol);

    console.log(`[UniverseWorker] Universe built: ${activeSymbols.length} active equities.`);

    await supabase.from('analysis_runs').update({
        current_stage: 'INGESTION',
        universe_size: activeSymbols.length
    }).eq('id', runId);

    const chunkSize = 200;
    for (let i = 0; i < activeSymbols.length; i += chunkSize) {
        const chunk = activeSymbols.slice(i, i + chunkSize);
        await ingestionQueue.add('ingest_batch', { runId, symbols: chunk }, {
            attempts: 2,
            backoff: { type: 'exponential', delay: 5000 }
        });
    }
}, { connection });

// ─────────────────────────────────────────────────────────
// STAGE 2: INGESTION — Verify data freshness, fetch if stale
// ─────────────────────────────────────────────────────────
const ingestionWorker = new Worker('IngestionQueue', async (job) => {
    const { runId, symbols } = job.data;
    console.log(`[IngestionWorker] Verifying/ingesting OHLCV for ${symbols.length} stocks...`);

    const today = new Date().toISOString().split('T')[0];

    for (const symbol of symbols) {
        console.log(`[IngestionWorker] Processing data for: ${symbol}`);
        try {
            const { data: existing } = await supabase
                .from('daily_ohlcv')
                .select('date')
                .eq('symbol', symbol)
                .order('date', { ascending: false })
                .limit(1);

            let needsUpdate = true;
            if (existing && existing.length > 0) {
                const lastDate = new Date(existing[0].date);
                const now = new Date();
                const diffMs = now - lastDate;
                if (diffMs < 1000 * 60 * 60 * 24 * 2) { // 48 hours
                    needsUpdate = false;
                }
            }

            if (!needsUpdate) continue;

            const { count } = await supabase
                .from('daily_ohlcv')
                .select('*', { count: 'exact', head: true })
                .eq('symbol', symbol);

            const endDate = new Date();
            const startDate = new Date();
            if (count < 250) {
                startDate.setFullYear(endDate.getFullYear() - 1);
            } else {
                startDate.setDate(endDate.getDate() - 5);
            }

            const data = await acquisitionManager.fetchHistoricalOHLCV(symbol, startDate, endDate);
            if (data && data.length > 0) {
                const mapped = data.map(q => ({
                    symbol: q.symbol, date: q.date,
                    open: q.open, high: q.high, low: q.low, close: q.close,
                    volume: q.volume, traded_value: q.traded_value
                }));
                await supabase.from('daily_ohlcv').upsert(mapped, { onConflict: 'symbol,date' });
            }
        } catch (e) {
            console.warn(`[IngestionWorker] Failed for ${symbol}: ${e.message}`);
            await supabase.from('security_master').update({ is_active: false }).eq('symbol', symbol);
        }
        await new Promise(r => setTimeout(r, 100 + Math.random() * 200));
    }

    // Increment processed_symbols for this run in Redis
    try {
        await connection.incrby(`run:${runId}:processed_symbols`, symbols.length);
    } catch (e) {
        console.warn(`[IngestionWorker] Failed to update processed_symbols in Redis: ${e.message}`);
    }

    await computeQueue.add('compute_features', { runId, symbols }, {
        attempts: 2
    });
}, { connection, concurrency: 3 });

// ─────────────────────────────────────────────────────────
// STAGE 3: COMPUTE — Strict Liquidity & Momentum Gate
// ─────────────────────────────────────────────────────────
const computeWorker = new Worker('ComputeQueue', async (job) => {
    const { runId, symbols } = job.data;
    
    let niftyPrices = [];
    let smallcapPrices = [];
    let midcapPrices = [];
    
    try {
        const endDate = new Date();
        const startDate = new Date();
        startDate.setFullYear(endDate.getFullYear() - 2);
        
        const [niftyDataRaw, scData, mcData] = await Promise.all([
            yahooFinance.historical('^NSEI', { period1: startDate, period2: endDate, interval: '1d' }).catch(() => []),
            yahooFinance.historical('^CNXSC', { period1: startDate, period2: endDate, interval: '1d' }).catch(() => []),
            yahooFinance.historical('^CNXMC', { period1: startDate, period2: endDate, interval: '1d' }).catch(() => [])
        ]);
        
        if (niftyDataRaw && niftyDataRaw.length > 0) niftyPrices = niftyDataRaw.map(d => d.close);
        if (scData && scData.length > 0) smallcapPrices = scData.map(d => d.close);
        if (mcData && mcData.length > 0) midcapPrices = mcData.map(d => d.close);

    } catch (e) {
        console.warn('[ComputeWorker] Failed to fetch benchmarks.');
    }

    const today = new Date().toISOString().split('T')[0];
    const qualifiedSymbols = [];

    for (const symbol of symbols) {
        console.log(`[ComputeWorker] Running momentum gate on: ${symbol}`);
        try {
            // ETF / MF / Bond Exclusion Filter (cheap check first)
            if (symbol.includes('ETF') || symbol.includes('BEES') || symbol.includes('LIQUID') || 
                symbol.includes('GOLD') || symbol.includes('SILVER') || symbol.includes('NIFTYBEES') ||
                symbol.endsWith('MF') || symbol.includes('BOND')) continue;

            const { data: ohlcv } = await supabase
                .from('daily_ohlcv')
                .select('date, open, high, low, close, volume, traded_value')
                .eq('symbol', symbol)
                .order('date', { ascending: true })
                .limit(500);

            if (!ohlcv || ohlcv.length < 200) continue; // Require at least 200 days for Stage 2 checks

            const closes = ohlcv.map(d => d.close);
            const currentPrice = closes[closes.length - 1];

            // 1. Minimum Price Filter (avoid penny stocks)
            if (currentPrice < 20) continue;

            // 2. Liquidity Filter (Avg Traded Value > ₹10 Cr)
            const recent20 = ohlcv.slice(-20);
            const avgTradedValue = recent20.reduce((sum, d) => sum + (d.traded_value || d.close * d.volume), 0) / recent20.length;
            if (avgTradedValue < 100000000) continue;

            // 3. Relative Volume check
            const relVol = FeatureEngine.computeRelativeVolume(ohlcv, 20);

            // 4. Weinstein Stage 2 Check (Price > 50SMA > 200SMA)
            const stage2 = FeatureEngine.checkWeinsteinStage2(closes);
            
            // 5. Multi-Timeframe: Price must also be above 20 EMA (short-term trend)
            const ema20 = FeatureEngine.computeEMA(closes, 20);
            const aboveEMA20 = ema20 ? currentPrice > ema20 : false;

            // 6. Compute RSI & OBV
            const rsi = FeatureEngine.computeRSI(closes, 14);
            const isOBVRising = FeatureEngine.isOBVRising(ohlcv, 20);

            // 7. Accumulation/Distribution: Volume on up-days must exceed volume on down-days
            let upDayVol = 0, downDayVol = 0, upDays = 0, downDays = 0;
            for (const bar of recent20) {
                if (bar.close >= bar.open) { upDayVol += bar.volume; upDays++; }
                else { downDayVol += bar.volume; downDays++; }
            }
            const accumRatio = downDayVol > 0 ? upDayVol / downDayVol : 2.0;

            // RS against Appropriate Benchmark
            let benchmarkPrices = niftyPrices; // Default large cap
            if (avgTradedValue <= 500000000 && smallcapPrices.length > 66) {
                benchmarkPrices = smallcapPrices;
            } else if (avgTradedValue > 500000000 && avgTradedValue <= 2000000000 && midcapPrices.length > 66) {
                benchmarkPrices = midcapPrices;
            }

            let rs3m = 1.0;
            if (benchmarkPrices && benchmarkPrices.length > 66) {
                rs3m = FeatureEngine.computeRelativeStrength(closes, benchmarkPrices, 66);
            }

            // Persist features
            await supabase.from('stock_features').upsert({
                symbol, date: today,
                rs_3m: rs3m,
                atr_20: TechnicalEngine.computeATR(ohlcv, 20),
                cmf_20: TechnicalEngine.computeCMF(ohlcv, 20),
                trend_quality_score: stage2.isStage2 ? 80 : 30
            }, { onConflict: 'symbol,date' });

            // ── GATE ── Strict multi-factor filter
            if (
                stage2.conditions.aboveSMA50 && 
                stage2.conditions.aboveSMA200 &&
                (stage2.conditions.sma50AboveSMA200 || stage2.conditions.aboveSMA150) && // Allow early Stage 2 transitions
                (stage2.conditions.sma50Rising || stage2.conditions.sma150Rising) &&     // Trend is flattening/turning up
                aboveEMA20 &&                                                            // Short-term trend intact
                rs3m > 1.05 &&                                                           // STRICT: Must outperform benchmark by at least 5% over 3 months
                (isOBVRising || accumRatio > 1.0) &&                                     // Smart money accumulation
                rsi > 40 && rsi < 90                                                     // Not oversold or hyper-extended
            ) {
                qualifiedSymbols.push({
                    symbol,
                    rs3m,
                    relVol,
                    isStage2: stage2.isStage2,
                    rsi,
                    isOBVRising,
                    accumRatio
                });
            }

        } catch (e) {
            console.warn(`[ComputeWorker] Error on ${symbol}: ${e.message}`);
        }
    }

    console.log(`[ComputeWorker] ${qualifiedSymbols.length}/${symbols.length} passed momentum gate.`);

    

    if (qualifiedSymbols.length > 0) {
        await deepAnalysisQueue.add('deep_analysis', { runId, symbols: qualifiedSymbols }, {
            attempts: 2
        });
    }
}, { connection, concurrency: 3 });

// ─────────────────────────────────────────────────────────
// STAGE 4: DEEP ANALYSIS — Patterns & Technical Setup Scan
// ─────────────────────────────────────────────────────────
const deepAnalysisWorker = new Worker('DeepAnalysisQueue', async (job) => {
    const { runId, symbols } = job.data;
    console.log(`[DeepAnalysisWorker] Scanning ${symbols.length} stocks for patterns...`);

    const passedCandidates = [];

    for (const cand of symbols) {
        console.log(`[DeepAnalysisWorker] Scanning patterns for: ${cand.symbol}`);
        try {
            const { data: ohlcv } = await supabase
                .from('daily_ohlcv')
                .select('date, open, high, low, close, volume')
                .eq('symbol', cand.symbol)
                .order('date', { ascending: true })
                .limit(500);

            if (!ohlcv) continue;

            const candleQuality = TechnicalEngine.candleQualityScore(ohlcv.slice(-10));
            const hasGapDown = TechnicalEngine.hasRecentGapDown(ohlcv, 5, 0.02);
            
            // If the chart is structurally broken with recent gaps, reject
            if (hasGapDown) continue;

            // Reject if today's candle is a massive red candle (false breakout indicator)
            const latestCandle = ohlcv[ohlcv.length - 1];
            const dailyReturn = (latestCandle.close - latestCandle.open) / latestCandle.open;
            if (dailyReturn < -0.02) continue; // Dropped more than 2% intraday

            // Volume analysis: check for volume dry-up in base (VCP signature)
            const isBaseDry = FeatureEngine.isVolumeDryingUp(ohlcv, 20);

            // Pattern Detection
            const vcp = PatternEngine.detectVCP(ohlcv);
            const flatBase = PatternEngine.detectFlatBase(ohlcv);
            const ath = PatternEngine.detectATHBreakout(ohlcv);
            const h52 = PatternEngine.detect52WeekHighProximity(ohlcv);
            const cup = PatternEngine.detectCupAndHandle(ohlcv);
            const ascTriangle = PatternEngine.detectAscendingTriangle(ohlcv);
            const hhhl = PatternEngine.detectHigherHighHigherLow(ohlcv);
            const nr7 = FeatureEngine.detectNR7(ohlcv);
            const insideBar = FeatureEngine.detectInsideBar(ohlcv);
            const pocketPivot = TechnicalEngine.detectPocketPivot(ohlcv);

            let setupType = null;
            let pivotPrice = null;
            let setupQuality = candleQuality; // Start with candle quality (0-100)

            // Boost quality for setups that have confirmed volume dry-up (institutional accumulation)
            if (isBaseDry) setupQuality = Math.min(100, setupQuality + 15);

            if (ath.isATH) {
                setupType = 'ATH_BREAKOUT';
                pivotPrice = ath.pivot;
            } else if (cup.isCupAndHandle) {
                setupType = 'CUP_AND_HANDLE';
                pivotPrice = cup.pivot;
            } else if (vcp.isVCP) {
                setupType = 'VCP_BREAKOUT';
                pivotPrice = vcp.pivot;
            } else if (ascTriangle.isAscendingTriangle) {
                setupType = 'ASCENDING_TRIANGLE';
                pivotPrice = ascTriangle.pivot;
            } else if (flatBase.isFlatBase) {
                setupType = 'FLAT_BASE';
                pivotPrice = flatBase.pivot;
            } else if (insideBar.isInsideBar && cand.isStage2) {
                setupType = 'INSIDE_BAR';
                pivotPrice = insideBar.motherBar.high;
            } else if (nr7 && cand.isStage2) {
                setupType = 'NR7_CONTRACTION';
                pivotPrice = Math.max(...ohlcv.slice(-2).map(q => q.high));
            } else if (pocketPivot.isPocketPivot && cand.isStage2) {
                setupType = 'POCKET_PIVOT';
                pivotPrice = pocketPivot.price;
            } else if (hhhl.isHHHL && cand.isStage2) {
                setupType = 'HH_HL_TREND';
                pivotPrice = hhhl.pivot;
            } else if (h52.is52WHigh) {
                setupType = '52W_HIGH';
                pivotPrice = h52.pivot;
            }

            if (setupType && pivotPrice) {
                passedCandidates.push({
                    symbol: cand.symbol,
                    setupType,
                    setupQuality,
                    pivotPrice,
                    rs3m: cand.rs3m,
                    relVol: cand.relVol,
                    rsi: cand.rsi,
                    isOBVRising: cand.isOBVRising,
                    accumRatio: cand.accumRatio || 1.0
                });
            }
        } catch (e) {
            console.warn(`[DeepAnalysisWorker] Error on ${cand.symbol}: ${e.message}`);
        }
    }

    console.log(`[DeepAnalysisWorker] ${passedCandidates.length} found with valid setups.`);

    if (passedCandidates.length > 0) {
        await fundamentalQueue.add('fundamental_scan', { runId, candidates: passedCandidates }, {
            attempts: 2
        });
    }
}, { connection, concurrency: 2 });

// ─────────────────────────────────────────────────────────
// STAGE 5: FUNDAMENTALS — Fetch Financials from Yahoo
// ─────────────────────────────────────────────────────────
const fundamentalWorker = new Worker('FundamentalQueue', async (job) => {
    const { runId, candidates } = job.data;
    console.log(`[FundamentalWorker] Fetching financials for ${candidates.length} stocks...`);

    

    const candidatesForFusion = [];

    for (const cand of candidates) {
        console.log(`[FundamentalWorker] Fetching financials for: ${cand.symbol}`);
        try {
            const fundamentals = await FundamentalEngine.scoreFundamentals(cand.symbol);
            
            // Delay to avoid hitting Yahoo Finance rate limits
            await new Promise(r => setTimeout(r, 1000 + Math.random() * 500));

            candidatesForFusion.push({
                ...cand,
                fundamentals
            });
        } catch (e) {
            console.warn(`[FundamentalWorker] Failed for ${cand.symbol}`);
            candidatesForFusion.push({ ...cand, fundamentals: { score: 30, metrics: null } });
        }
    }

    if (candidatesForFusion.length > 0) {
        await sentimentQueue.add('sentiment_scan', { runId, candidates: candidatesForFusion }, { attempts: 2 });
    }
}, { connection, concurrency: 1 });

// ─────────────────────────────────────────────────────────
// STAGE 5b: SENTIMENT — Fetch latest documents and filings
// ─────────────────────────────────────────────────────────
const sentimentWorker = new Worker('SentimentQueue', async (job) => {
    const { runId, candidates } = job.data;
    console.log(`[SentimentWorker] Fetching document intelligence for ${candidates.length} stocks...`);

    

    const candidatesWithSentiment = [];

    for (const cand of candidates) {
        console.log(`[SentimentWorker] Scanning docs/filings for: ${cand.symbol}`);
        try {
            const intel = await docIntelPipeline.getCompanyIntel(cand.symbol, { forceRefresh: true });
            
            // Extract highly confident facts
            const facts = [];
            if (intel && intel.length > 0) {
                intel.forEach(doc => {
                    if (doc.extracted_facts && doc.confidence === 'HIGH') {
                        facts.push(...doc.extracted_facts);
                    }
                });
            }

            candidatesWithSentiment.push({
                ...cand,
                facts
            });
        } catch (e) {
            console.warn(`[SentimentWorker] Failed for ${cand.symbol}`);
            candidatesWithSentiment.push({ ...cand, facts: [] });
        }
    }

    if (candidatesWithSentiment.length > 0) {
        await fusionQueue.add('evidence_fusion', { runId, candidates: candidatesWithSentiment }, { attempts: 2 });
    }
}, { connection, concurrency: 2 });

// ─────────────────────────────────────────────────────────
// STAGE 6: FUSION — Score, validate R/R, generate thesis
// ─────────────────────────────────────────────────────────
const fusionWorker = new Worker('FusionQueue', async (job) => {
    const { runId, candidates } = job.data;
    console.log(`[FusionWorker] Fusing data for ${candidates.length} candidates...`);

    

    const regime = await regimeEngine.fetchAndClassify(supabase);
    const today = new Date().toISOString().split('T')[0];

    for (const cand of candidates) {
        console.log(`[FusionWorker] Generating trade plan for: ${cand.symbol}`);
        try {
            // Fetch enough data for both ATR and sector rotation comparison
            const { data: recentOhlcvDesc } = await supabase
                .from('daily_ohlcv')
                .select('date, open, high, low, close')
                .eq('symbol', cand.symbol)
                .order('date', { ascending: false })
                .limit(250);

            if (!recentOhlcvDesc || recentOhlcvDesc.length < 20) continue;

            const currentPrice = recentOhlcvDesc[0].close;
            // Create ascending copy for ATR without mutating original
            const recentOhlcvAsc = [...recentOhlcvDesc].reverse();
            const atr = TechnicalEngine.computeATR(recentOhlcvAsc, 20) || (currentPrice * 0.03);

            const entryTrigger = cand.pivotPrice;
            // Use the MOST RECENT 10 bars (descending) for structural low
            const structuralLow = Math.min(...recentOhlcvDesc.slice(0, 10).map(d => d.low));
            const stopLoss = Math.max(structuralLow, entryTrigger - (atr * 1.5));
            const target1 = entryTrigger + ((entryTrigger - stopLoss) * 2.0);
            const target2 = entryTrigger + ((entryTrigger - stopLoss) * 3.5);

            const riskPerShare = entryTrigger - stopLoss;
            const rewardPerShare = target1 - entryTrigger;
            const riskReward = riskPerShare > 0 ? rewardPerShare / riskPerShare : 0;

            // Compute sector rotation score using proper length comparison
            let sectorScore = 50;
            try {
                const endDate = new Date();
                const startDate = new Date();
                startDate.setFullYear(endDate.getFullYear() - 1);
                
                const niftyOhlcvRaw = await yahooFinance.historical('^NSEI', { period1: startDate, period2: endDate, interval: '1d' }).catch(() => []);
                
                if (niftyOhlcvRaw && niftyOhlcvRaw.length > 60) {
                    // Create date-keyed map for Nifty closes
                    const niftyMap = new Map();
                    niftyOhlcvRaw.forEach(d => {
                        const dStr = new Date(d.date).toISOString().split('T')[0];
                        niftyMap.set(dStr, d.close);
                    });
                    
                    const niftyReturns = [];
                    const stockReturns = [];
                    
                    for (let i = 1; i < recentOhlcvAsc.length; i++) {
                        const currDate = recentOhlcvAsc[i].date;
                        const prevDate = recentOhlcvAsc[i-1].date;
                        
                        if (niftyMap.has(currDate) && niftyMap.has(prevDate)) {
                            const nCurr = niftyMap.get(currDate);
                            const nPrev = niftyMap.get(prevDate);
                            niftyReturns.push((nCurr - nPrev) / nPrev);
                            
                            const sCurr = recentOhlcvAsc[i].close;
                            const sPrev = recentOhlcvAsc[i-1].close;
                            stockReturns.push((sCurr - sPrev) / sPrev);
                        }
                    }
                    
                    const rotation = SectorRotationEngine.evaluateSector(stockReturns, niftyReturns);
                    sectorScore = rotation.score;
                }
            } catch (e) {
                // Fall back to neutral if sector analysis fails
            }

            const score = FusionEngine.generateOpportunityScore({
                regime: { state: regime.regime_state || 'NEUTRAL' },
                momentum: { rsPercentile: Math.min(100, cand.rs3m * 50), relVol: cand.relVol },
                technical: {
                    pattern: cand.setupType,
                    quality: cand.setupQuality,
                    isNearPivot: Math.abs(currentPrice - entryTrigger) / currentPrice < 0.03
                },
                fundamentals: { score: cand.fundamentals.score },
                sector: { score: sectorScore },
                facts: cand.facts || []
            });

            let readiness = FusionEngine.evaluateReadiness(score, currentPrice, entryTrigger, stopLoss, target1);
            if (readiness === 'REJECTED') continue; // Reject low R/R or low score trades completely

            const thesis = FusionEngine.generateThesis({
                momentum: { rsPercentile: Math.min(100, cand.rs3m * 50) },
                technical: { pattern: cand.setupType, quality: cand.setupQuality, pivot: entryTrigger },
                fundamentals: { score: cand.fundamentals.score }
            }, score, readiness);

            const { error } = await supabase.from('trade_plans').upsert({
                run_id: runId,
                symbol: cand.symbol,
                date: today,
                setup_type: cand.setupType,
                opportunity_score: score,
                trade_readiness: readiness,
                entry_trigger: entryTrigger,
                entry_high: entryTrigger * 1.01,
                stop_loss: stopLoss,
                target_1: target1,
                target_2: target2,
                risk_reward: riskReward,
                expected_horizon: '1-3 weeks',
                confidence: score / 100,
                thesis: thesis
            });

            if (error) {
                console.error(`[FusionWorker] Supabase upsert error for ${cand.symbol}:`, error);
            } else {
                console.log(`[FusionWorker] ✔ ${cand.symbol}: Score=${score.toFixed(1)}, Setup=${cand.setupType}, Readiness=${readiness}`);
            }
        } catch (e) {
            console.warn(`[FusionWorker] Error on ${cand.symbol}: ${e.message}`);
        }
    }

    // Mark pipeline as COMPLETED
    console.log(`[FusionWorker] Pipeline run ${runId} complete.`);
    // Pipeline completed logic handled by API endpoints
}, { connection });
