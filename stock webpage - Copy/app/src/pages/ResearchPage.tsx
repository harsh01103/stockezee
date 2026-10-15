import { useEffect, useState, useCallback } from 'react';
import {
    Brain, TrendingUp, Loader2, Target, ShieldAlert,
    BarChart2, Activity, CheckCircle2, XCircle, Clock,
    Layers, ChevronDown, ChevronUp, ExternalLink,
    Zap, Shield, AlertTriangle, Eye, Play
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';
import { LightweightChart } from '../components/LightweightChart';

/* ─── Types ─────────────────────────────────────────── */
interface TradePlan {
    id: string;
    symbol: string;
    date: string;
    setup_type: string;
    opportunity_score: number;
    trade_readiness: 'READY' | 'DEVELOPING' | 'EXTENDED' | 'NEAR_TRIGGER';
    entry_trigger: number;
    stop_loss: number;
    target_1: number;
    target_2: number;
    risk_reward: number;
    expected_horizon: string;
    confidence: number;
    thesis: {
        summary: string;
        bulletPoints: string[];
        score: string;
    };
    chart_annotations?: any[];
    fundamental_metrics?: any;
}

interface MarketRegime {
    regime_state: string;
    nifty_trend_score: number;
    breadth_above_50dma_pct: number;
    volatility_percentile: number;
}

/* ─── TradingView Widget ──────────────────────────── */

/** Normalize NSE symbol to a TradingView-compatible identifier.
 *  TradingView uses BSE: prefix for ETFs/mutual funds not listed on NSE feed,
 *  and some NSE symbols use a slightly different ticker. */
function normalizeTVSymbol(raw: string): string {
    const s = raw.toUpperCase();
    // ETF / liquid-bees style funds are often only on BSE on TradingView
    const bseOnlyPatterns = ['ETF', 'BEES', 'LIQUID', 'GOLD1', 'SILVER', 'TATAGOLD', 'TATSILV',
        'CASHIETF', 'METALIETF', 'PVTBANIETF', 'LIQUIDADD', 'HDFCSILVER', 'HDFCSML'];
    if (bseOnlyPatterns.some(p => s.includes(p))) return `BSE:${s}`;
    return `NSE:${s}`;
}

function TradingViewWidget({ symbol }: { symbol: string }) {
    useEffect(() => {
        const container = document.getElementById('tv-widget-container');
        if (!container) return;
        container.innerHTML = '';

        const tvSymbol = normalizeTVSymbol(symbol);

        const script = document.createElement('script');
        script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
        script.type = 'text/javascript';
        script.async = true;
        script.innerHTML = JSON.stringify({
            autosize: true,
            symbol: tvSymbol,
            interval: 'D',
            timezone: 'Asia/Kolkata',
            theme: 'dark',
            style: '1',
            locale: 'en',
            backgroundColor: 'rgba(5, 5, 5, 1)',
            gridColor: 'rgba(30, 41, 59, 0.5)',
            allow_symbol_change: true,
            calendar: false,
            support_host: 'https://www.tradingview.com',
            studies: ['MASimple@tv-basicstudies', 'RSI@tv-basicstudies', 'Volume@tv-basicstudies'],
            height: '100%',
            width: '100%'
        });

        container.appendChild(script);
    }, [symbol]);

    return (
        <div className="rounded-xl overflow-hidden border border-slate-700/50 bg-[#050505]" style={{ height: '500px' }}>
            <div id="tv-widget-container" style={{ height: '100%', width: '100%' }} />
        </div>
    );
}

/* ─── Readiness Badge ─────────────────────────────── */
function ReadinessBadge({ readiness }: { readiness: string }) {
    const configs: Record<string, { bg: string; text: string; icon: any; label: string }> = {
        READY: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', icon: CheckCircle2, label: 'Ready' },
        NEAR_TRIGGER: { bg: 'bg-amber-500/20', text: 'text-amber-400', icon: Zap, label: 'Near Trigger' },
        DEVELOPING: { bg: 'bg-blue-500/20', text: 'text-blue-400', icon: Clock, label: 'Developing' },
        EXTENDED: { bg: 'bg-red-500/20', text: 'text-red-400', icon: AlertTriangle, label: 'Extended' },
    };
    const cfg = configs[readiness] || configs.DEVELOPING;
    const Icon = cfg.icon;

    return (
        <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${cfg.bg} ${cfg.text}`}>
            <Icon className="w-3 h-3" />
            {cfg.label}
        </span>
    );
}

/* ─── Setup Type Badge ────────────────────────────── */
function SetupBadge({ type }: { type: string }) {
    const label = type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-violet-500/20 text-violet-300 border border-violet-500/30">
            <Layers className="w-3 h-3" />
            {label}
        </span>
    );
}

/* ─── Regime Card ─────────────────────────────────── */
function RegimeCard({ regime }: { regime: MarketRegime | null }) {
    if (!regime) return null;

    const stateColors: Record<string, string> = {
        STRONG_RISK_ON: 'text-emerald-400',
        RISK_ON: 'text-green-400',
        SELECTIVE_BULL: 'text-lime-400',
        NEUTRAL: 'text-slate-400',
        SELECTIVE_BEAR: 'text-orange-400',
        RISK_OFF: 'text-red-400',
    };

    return (
        <div className="bg-[#0a0a0a] rounded-2xl border border-slate-800 p-5">
            <div className="flex items-center gap-2 mb-3">
                <Activity className="w-5 h-5 text-cyan-400" />
                <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Market Regime</h3>
            </div>
            <div className={`text-2xl font-black ${stateColors[regime.regime_state] || 'text-slate-400'}`}>
                {regime.regime_state.replace(/_/g, ' ')}
            </div>
            <div className="grid grid-cols-3 gap-3 mt-4">
                <div className="bg-slate-900/50 rounded-lg p-2.5 text-center">
                    <div className="text-[10px] text-slate-500 uppercase">Trend</div>
                    <div className="text-lg font-bold text-white">{regime.nifty_trend_score?.toFixed(0) || '—'}</div>
                </div>
                <div className="bg-slate-900/50 rounded-lg p-2.5 text-center">
                    <div className="text-[10px] text-slate-500 uppercase">Breadth</div>
                    <div className="text-lg font-bold text-white">{regime.breadth_above_50dma_pct?.toFixed(0) || '—'}%</div>
                </div>
                <div className="bg-slate-900/50 rounded-lg p-2.5 text-center">
                    <div className="text-[10px] text-slate-500 uppercase">Vol %ile</div>
                    <div className="text-lg font-bold text-white">{regime.volatility_percentile?.toFixed(0) || '—'}</div>
                </div>
            </div>
        </div>
    );
}

/* ─── Stock Card ──────────────────────────────────── */
function StockCard({ plan, onSelect, isSelected }: { plan: TradePlan; onSelect: () => void; isSelected: boolean }) {
    const [expanded, setExpanded] = useState(false);
    const rr = plan.risk_reward?.toFixed(1) || '—';

    return (
        <motion.div
            layout
            className={`bg-[#0a0a0a] rounded-2xl border transition-all duration-300 cursor-pointer ${isSelected ? 'border-emerald-500/60 shadow-lg shadow-emerald-500/10' : 'border-slate-800 hover:border-slate-600'}`}
            onClick={onSelect}
        >
            <div className="p-5">
                {/* Header */}
                <div className="flex items-start justify-between mb-3">
                    <div>
                        <div className="flex items-center gap-2.5 mb-1">
                            <span className="text-lg font-black text-white">{plan.symbol}</span>
                            <ReadinessBadge readiness={plan.trade_readiness} />
                        </div>
                        <SetupBadge type={plan.setup_type} />
                    </div>
                    <div className="text-right">
                        <div className="text-3xl font-black text-white">{plan.opportunity_score?.toFixed(0)}</div>
                        <div className="text-[10px] text-slate-500 uppercase tracking-wider">Score</div>
                    </div>
                </div>

                {/* Fundamentals Quick View */}
                {plan.fundamental_metrics && plan.fundamental_metrics.peRatio && (
                    <div className="flex gap-2 mt-2 mb-2">
                        <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                            P/E: {plan.fundamental_metrics.peRatio.toFixed(1)}
                        </span>
                        {plan.fundamental_metrics.roe && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                                ROE: {(plan.fundamental_metrics.roe * 100).toFixed(1)}%
                            </span>
                        )}
                        {plan.fundamental_metrics.revenueGrowth && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                                Rev Growth: {(plan.fundamental_metrics.revenueGrowth * 100).toFixed(1)}%
                            </span>
                        )}
                    </div>
                )}

                {/* Levels Grid */}
                <div className="grid grid-cols-4 gap-2 mt-4">
                    <div className="bg-emerald-500/10 rounded-lg p-2 text-center">
                        <div className="text-[9px] text-emerald-400/70 uppercase font-bold">Entry</div>
                        <div className="text-sm font-bold text-emerald-400">₹{plan.entry_trigger?.toFixed(1)}</div>
                    </div>
                    <div className="bg-red-500/10 rounded-lg p-2 text-center">
                        <div className="text-[9px] text-red-400/70 uppercase font-bold">Stop</div>
                        <div className="text-sm font-bold text-red-400">₹{plan.stop_loss?.toFixed(1)}</div>
                    </div>
                    <div className="bg-cyan-500/10 rounded-lg p-2 text-center">
                        <div className="text-[9px] text-cyan-400/70 uppercase font-bold">Target</div>
                        <div className="text-sm font-bold text-cyan-400">₹{plan.target_1?.toFixed(1)}</div>
                    </div>
                    <div className="bg-violet-500/10 rounded-lg p-2 text-center">
                        <div className="text-[9px] text-violet-400/70 uppercase font-bold">R:R</div>
                        <div className={`text-sm font-bold ${Number(rr) >= 2 ? 'text-emerald-400' : 'text-amber-400'}`}>{rr}</div>
                    </div>
                </div>

                {/* Expand Toggle */}
                <button
                    onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
                    className="flex items-center gap-1 mt-3 text-xs text-slate-500 hover:text-white transition-colors"
                >
                    {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    {expanded ? 'Hide' : 'Show'} Analysis
                </button>

                {/* Thesis */}
                <AnimatePresence>
                    {expanded && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                        >
                            <div className="mt-3 pt-3 border-t border-slate-800">
                                <p className="text-sm text-slate-300 leading-relaxed">
                                    {plan.thesis?.summary || 'No analysis available.'}
                                </p>
                                {plan.thesis?.bulletPoints && (
                                    <ul className="mt-2 space-y-1">
                                        {plan.thesis.bulletPoints.map((bp, i) => (
                                            <li key={i} className="flex items-start gap-2 text-xs text-slate-400">
                                                <CheckCircle2 className="w-3 h-3 mt-0.5 text-emerald-500 shrink-0" />
                                                {bp}
                                            </li>
                                        ))}
                                    </ul>
                                )}
                                <div className="flex items-center gap-4 mt-3 text-[10px] text-slate-600">
                                    <span>Horizon: {plan.expected_horizon || '—'}</span>
                                    <span>Confidence: {(plan.confidence * 100)?.toFixed(0)}%</span>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </motion.div>
    );
}

/* ─── Main Page ──────────────────────────────────── */
export function ResearchPage() {
    const [watchlist, setWatchlist] = useState<TradePlan[]>([]);
    const [regime, setRegime] = useState<MarketRegime | null>(null);
    const [loading, setLoading] = useState(true);
    const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
    const [horizon, setHorizon] = useState<'all' | 'next_session' | 'next_week'>('all');
    const [isPipelineRunning, setIsPipelineRunning] = useState(false);
    const [pipelineRun, setPipelineRun] = useState<any>(null);
    const [selectedStockData, setSelectedStockData] = useState<any>(null);

    const fetchStatus = useCallback(async () => {
        try {
            const res = await axios.get('http://localhost:4000/api/research/status');
            if (res.data.success && res.data.run) {
                setPipelineRun(res.data.run);
                if (res.data.run.status === 'RUNNING') {
                    setIsPipelineRunning(true);
                } else {
                    setIsPipelineRunning(false);
                }
            }
        } catch (err) {
            console.error('Failed to fetch pipeline status:', err);
        }
    }, []);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [watchlistRes, regimeRes] = await Promise.all([
                axios.get(`http://localhost:4000/api/research/watchlist?horizon=${horizon}`),
                axios.get('http://localhost:4000/api/research/regime')
            ]);
            if (watchlistRes.data.success) setWatchlist(watchlistRes.data.watchlist || []);
            if (regimeRes.data.success) setRegime(regimeRes.data.regime || null);
        } catch (err) {
            console.error('Failed to fetch research data:', err);
        } finally {
            setLoading(false);
        }
    }, [horizon]);

    useEffect(() => { fetchData(); fetchStatus(); }, [fetchData, fetchStatus]);

    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (isPipelineRunning) {
            interval = setInterval(fetchStatus, 3000);
        }
        return () => {
            if (interval) clearInterval(interval);
        };
    }, [isPipelineRunning, fetchStatus]);

    const handleSelectStock = async (symbol: string) => {
        setSelectedSymbol(symbol);
        setSelectedStockData(null);
        try {
            const res = await axios.get(`http://localhost:4000/api/research/stock/${symbol}`);
            if (res.data.success) {
                setSelectedStockData(res.data);
            }
        } catch (err) {
            console.error('Failed to fetch stock details:', err);
        }
    };

    const readyCount = watchlist.filter(w => w.trade_readiness === 'READY').length;
    const devCount = watchlist.filter(w => w.trade_readiness === 'DEVELOPING').length;

    const handleRunPipeline = async () => {
        setIsPipelineRunning(true);
        try {
            const res = await axios.post('http://localhost:4000/api/research/run');
            if (res.data.success) {
                fetchStatus();
            } else {
                alert('Failed to start pipeline: ' + res.data.error);
                setIsPipelineRunning(false);
            }
        } catch (err: any) {
            alert('Error triggering pipeline: ' + (err.response?.data?.error || err.message));
            setIsPipelineRunning(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#050505] px-4 py-6 max-w-7xl mx-auto">
            {/* Page Header */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-600 to-cyan-500 flex items-center justify-center">
                        <Brain className="w-6 h-6 text-white" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-black text-white tracking-tight">Deep Research Engine</h1>
                        <p className="text-xs text-slate-500">Indian Equity Swing & Momentum Intelligence</p>
                    </div>
                </div>
                {/* Horizon Tabs */}
                <div className="flex gap-1 bg-slate-900 rounded-xl p-1">
                    {[
                        { key: 'all', label: 'All' },
                        { key: 'next_session', label: 'Next Session' },
                        { key: 'next_week', label: 'Next Week' },
                    ].map(tab => (
                        <button
                            key={tab.key}
                            onClick={() => setHorizon(tab.key as any)}
                            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all ${horizon === tab.key
                                ? 'bg-emerald-500/20 text-emerald-400'
                                : 'text-slate-500 hover:text-white hover:bg-white/5'
                            }`}
                        >
                            {tab.label}
                        </button>
                    ))}
                    <button
                        onClick={handleRunPipeline}
                        disabled={isPipelineRunning}
                        className={`ml-2 px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
                            isPipelineRunning 
                                ? 'bg-slate-800 text-slate-500 cursor-not-allowed' 
                                : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-500/20'
                        }`}
                    >
                        {isPipelineRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                        {isPipelineRunning ? 'Running...' : 'Run Pipeline'}
                    </button>
                </div>
            </div>


            {/* Pipeline 6-Stage Progress Tracker */}
            {pipelineRun && pipelineRun.status === 'RUNNING' && (() => {
                const stages = [
                    { key: 'UNIVERSE', label: '1. Universe', desc: 'Building equity list' },
                    { key: 'INGESTION', label: '2. Ingestion', desc: 'Fetching OHLCV data' },
                    { key: 'COMPUTE', label: '3. Momentum Gate', desc: 'Liquidity & trend filters' },
                    { key: 'DEEP_ANALYSIS', label: '4. Technical Scan', desc: 'Pattern detection' },
                    { key: 'FUNDAMENTALS', label: '5. Fundamentals', desc: 'Financial health scoring' },
                    { key: 'SENTIMENT', label: '6. Sentiment', desc: 'DocIntel & filings' },
                    { key: 'FUSION', label: '7. Fusion', desc: 'Score & trade plan' },
                ];
                const stageOrder = stages.map(s => s.key);
                const currentIdx = stageOrder.indexOf(pipelineRun.current_stage);
                return (
                    <div className="mb-6 bg-slate-900 border border-slate-800 rounded-xl p-5 overflow-hidden relative">
                        <div className="flex items-center gap-2 mb-4">
                            <Activity className="w-4 h-4 text-emerald-500 animate-pulse" />
                            <span className="text-slate-300 font-semibold tracking-wide text-xs uppercase">
                                Pipeline Running — Stage {currentIdx + 1}/{stages.length}
                            </span>
                            <span className="ml-auto text-xs text-slate-500 font-mono">
                                {pipelineRun.current_stage === 'UNIVERSE' ? 'Building Universe...' :
                                 `${pipelineRun.processed_symbols || 0} / ${pipelineRun.universe_size || 7500} stocks`}
                            </span>
                        </div>
                        <div className="flex gap-1.5">
                            {stages.map((stage, i) => {
                                const isActive = i === currentIdx;
                                const isCompleted = i < currentIdx;
                                return (
                                    <div key={stage.key} className="flex-1 relative">
                                        <div className={`h-1.5 rounded-full transition-all duration-500 ${
                                            isCompleted ? 'bg-emerald-500' :
                                            isActive ? 'bg-emerald-500 animate-pulse' :
                                            'bg-slate-800'
                                        }`} />
                                        <div className={`mt-2 text-center transition-colors ${
                                            isActive ? 'text-emerald-400' :
                                            isCompleted ? 'text-slate-400' :
                                            'text-slate-700'
                                        }`}>
                                            <div className="text-[9px] font-bold uppercase tracking-wider">{stage.label}</div>
                                            <div className="text-[8px] mt-0.5 hidden lg:block">{stage.desc}</div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                );
            })()}

            {/* Stats Bar */}
            <div className="grid grid-cols-4 gap-3 mb-6">
                <div className="bg-[#0a0a0a] rounded-xl border border-slate-800 p-4 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                        <Target className="w-5 h-5 text-emerald-400" />
                    </div>
                    <div>
                        <div className="text-2xl font-black text-white">{readyCount}</div>
                        <div className="text-[10px] text-slate-500 uppercase tracking-wider">Ready Now</div>
                    </div>
                </div>
                <div className="bg-[#0a0a0a] rounded-xl border border-slate-800 p-4 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                        <Eye className="w-5 h-5 text-blue-400" />
                    </div>
                    <div>
                        <div className="text-2xl font-black text-white">{devCount}</div>
                        <div className="text-[10px] text-slate-500 uppercase tracking-wider">Developing</div>
                    </div>
                </div>
                <div className="bg-[#0a0a0a] rounded-xl border border-slate-800 p-4 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-violet-500/10 flex items-center justify-center">
                        <BarChart2 className="w-5 h-5 text-violet-400" />
                    </div>
                    <div>
                        <div className="text-2xl font-black text-white">{watchlist.length}</div>
                        <div className="text-[10px] text-slate-500 uppercase tracking-wider">Total Setups</div>
                    </div>
                </div>
                <RegimeCard regime={regime} />
            </div>

            {/* Main Content */}
            {loading ? (
                <div className="flex flex-col items-center justify-center py-20">
                    <Loader2 className="w-10 h-10 text-emerald-500 animate-spin mb-4" />
                    <p className="text-slate-500 text-sm">Loading Deep Research Intelligence...</p>
                </div>
            ) : watchlist.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 bg-[#0a0a0a] rounded-2xl border border-slate-800">
                    <ShieldAlert className="w-12 h-12 text-amber-500/50 mb-4" />
                    <h3 className="text-lg font-bold text-white mb-1">No High-Conviction Setups</h3>
                    <p className="text-sm text-slate-500 max-w-md text-center">
                        The research engine found no stocks meeting the strict quality, liquidity, and pattern criteria. This is intentional — the system refuses to force trades when conditions are poor.
                    </p>
                </div>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
                    {/* Left: Candidate List */}
                    <div className="lg:col-span-2 space-y-3 max-h-[calc(100vh-280px)] overflow-y-auto pr-2 custom-scrollbar">
                        {watchlist.map(plan => (
                            <StockCard
                                key={plan.id || plan.symbol}
                                plan={plan}
                                onSelect={() => handleSelectStock(plan.symbol)}
                                isSelected={selectedSymbol === plan.symbol}
                            />
                        ))}
                    </div>

                    {/* Right: TradingView Chart */}
                    <div className="lg:col-span-3">
                        {selectedSymbol ? (
                            <div className="sticky top-24">
                                <div className="flex items-center gap-2 mb-3">
                                    <TrendingUp className="w-5 h-5 text-cyan-400" />
                                    <h2 className="text-lg font-bold text-white">{selectedSymbol}</h2>
                                    <a
                                        href={`https://www.tradingview.com/chart/?symbol=NSE:${selectedSymbol}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="ml-auto text-xs text-slate-500 hover:text-cyan-400 flex items-center gap-1"
                                    >
                                        Open in TradingView <ExternalLink className="w-3 h-3" />
                                    </a>
                                </div>
                                {selectedStockData && selectedStockData.ohlcv ? (
                                    <LightweightChart 
                                        data={selectedStockData.ohlcv} 
                                        annotations={selectedStockData.annotations ? JSON.parse(selectedStockData.annotations) : []}
                                        plan={selectedStockData.plan}
                                    />
                                ) : (
                                    <div className="flex flex-col items-center justify-center h-[500px] bg-[#0a0a0a] rounded-2xl border border-slate-800">
                                        <Loader2 className="w-8 h-8 text-slate-500 animate-spin mb-3" />
                                        <p className="text-sm text-slate-600">Loading Chart Data...</p>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center h-[500px] bg-[#0a0a0a] rounded-2xl border border-slate-800">
                                <BarChart2 className="w-12 h-12 text-slate-700 mb-3" />
                                <p className="text-sm text-slate-600">Select a stock to view the chart</p>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
