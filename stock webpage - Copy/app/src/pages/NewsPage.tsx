import { useEffect, useState } from 'react';
import { TrendingUp, Activity, Zap, BarChart2, AlertTriangle, RefreshCw, Loader2, Brain, BookOpen, Wrench, Target, ShieldAlert, ArrowUpRight, ExternalLink, X } from 'lucide-react';
import { useDemoStore } from '../store/demoStore';

interface KeyFactor {
    technical: string;
    simple: string;
}

interface TradeLevels {
    entry: number;
    target: number;
    stop_loss: number;
    target_pct: number;
    sl_pct: number;
    risk_reward: number;
}

interface ScreenedStock {
    symbol: string;
    name: string;
    market: string;
    probability: number;
    confidence: 'HIGH' | 'MEDIUM' | 'LOW';
    key_factors: KeyFactor[];
    why_it_can_rise: KeyFactor[];
    simple_summary: string;
    trade_levels: TradeLevels;
    metrics: {
        cmp: number;
        volume_ratio: number;
        rsi: number;
        ema_alignment: number;
        adx: number;
        atr_pct: number;
        return_1d: number;
        return_5d: number;
    };
}

interface NewsPageProps {
    onPageChange?: (page: any) => void;
}

export function NewsPage({ onPageChange }: NewsPageProps) {
    const [intradayResults, setIntradayResults] = useState<ScreenedStock[]>([]);
    const [swingResults, setSwingResults] = useState<ScreenedStock[]>([]);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState<'swing' | 'intraday'>('swing');
    const [selectedStock, setSelectedStock] = useState<ScreenedStock | null>(null);
    const [explainMode, setExplainMode] = useState<'simple' | 'technical'>('simple');
    const [universeSize, setUniverseSize] = useState(0);
    const [disclaimer, setDisclaimer] = useState('');
    const { setActiveSymbol } = useDemoStore();

    const fetchData = async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/news');
            const data = await res.json();
            setIntradayResults(data.intradaySetups || []);
            setSwingResults(data.swingSetups || []);
            setDisclaimer(data.disclaimer || '');
            setUniverseSize(data.universe_scanned || 300);
        } catch (err) {
            console.error(err);
        }
        setLoading(false);
    };

    useEffect(() => { fetchData(); }, []);

    const results = activeTab === 'intraday' ? intradayResults : swingResults;

    const confidenceColor = (c: string) => {
        if (c === 'HIGH') return 'text-emerald-400 bg-emerald-500/15 border-emerald-500/30';
        if (c === 'MEDIUM') return 'text-amber-400 bg-amber-500/15 border-amber-500/30';
        return 'text-slate-400 bg-slate-500/15 border-slate-500/30';
    };

    const probBarColor = (p: number) => {
        if (p >= 0.70) return 'bg-gradient-to-r from-emerald-600 to-emerald-400';
        if (p >= 0.50) return 'bg-gradient-to-r from-amber-600 to-amber-400';
        return 'bg-gradient-to-r from-slate-600 to-slate-400';
    };

    const probBarGlow = (p: number) => {
        if (p >= 0.70) return 'shadow-[0_0_12px_rgba(52,211,153,0.3)]';
        if (p >= 0.50) return 'shadow-[0_0_12px_rgba(251,191,36,0.2)]';
        return '';
    };

    const renderStockCard = (stock: ScreenedStock, index: number) => (
        <div
            key={stock.symbol}
            onClick={() => setSelectedStock(stock)}
            className={`p-5 rounded-2xl border transition-all cursor-pointer hover:scale-[1.01] ${selectedStock?.symbol === stock.symbol
                ? 'bg-emerald-500/10 border-emerald-500/40 ring-1 ring-emerald-500/30 shadow-lg shadow-emerald-500/10'
                : 'bg-[#1a1f36]/60 border-white/10 hover:border-white/20 hover:bg-[#1a1f36]/80'
                }`}
        >
            {/* Rank + Name */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-black ${index === 0 ? 'bg-amber-500/20 text-amber-400' : 'bg-white/5 text-white/40'
                        }`}>
                        {index + 1}
                    </div>
                    <div>
                        <h4
                            onClick={(e) => { e.stopPropagation(); setActiveSymbol(stock.symbol); if (onPageChange) onPageChange('demo'); }}
                            className="font-bold text-lg text-white hover:text-emerald-400 transition-colors cursor-pointer flex items-center gap-1.5 group/sym"
                        >
                            {stock.symbol}
                            <ExternalLink className="w-3 h-3 opacity-0 group-hover/sym:opacity-60 transition-opacity text-emerald-400" />
                        </h4>
                        <p className="text-xs text-white/40">{stock.name} · {stock.market}</p>
                    </div>
                </div>
                <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase border ${confidenceColor(stock.confidence)}`}>
                    {stock.confidence}
                </span>
            </div>

            {/* Probability Bar */}
            <div className="mb-3">
                <div className="flex justify-between items-center mb-1.5">
                    <span className="text-[10px] text-white/40 uppercase font-medium tracking-wider">Probability</span>
                    <span className={`text-lg font-black ${stock.probability >= 0.7 ? 'text-emerald-400' : stock.probability >= 0.5 ? 'text-amber-400' : 'text-white/60'}`}>
                        {(stock.probability * 100).toFixed(1)}%
                    </span>
                </div>
                <div className={`h-2.5 bg-white/5 rounded-full overflow-hidden ${probBarGlow(stock.probability)}`}>
                    <div
                        className={`h-full rounded-full transition-all duration-1000 ${probBarColor(stock.probability)}`}
                        style={{ width: `${stock.probability * 100}%` }}
                    />
                </div>
            </div>

            {/* Simple summary */}
            <p className="text-xs text-white/50 leading-relaxed mb-3 line-clamp-2">
                {stock.simple_summary}
            </p>

            {/* Entry / Target / SL */}
            {stock.trade_levels && (
                <div className="grid grid-cols-3 gap-2 pt-3 border-t border-white/5">
                    <div className="text-center">
                        <div className="text-[9px] text-white/30 uppercase">Entry</div>
                        <div className="text-sm font-bold text-white">₹{stock.trade_levels.entry}</div>
                    </div>
                    <div className="text-center">
                        <div className="text-[9px] text-emerald-400/60 uppercase">Target</div>
                        <div className="text-sm font-bold text-emerald-400">
                            ₹{stock.trade_levels.target}
                            <span className="text-[9px] ml-1 text-emerald-400/60">+{stock.trade_levels.target_pct}%</span>
                        </div>
                    </div>
                    <div className="text-center">
                        <div className="text-[9px] text-red-400/60 uppercase">Stop Loss</div>
                        <div className="text-sm font-bold text-red-400">
                            ₹{stock.trade_levels.stop_loss}
                            <span className="text-[9px] ml-1 text-red-400/60">-{stock.trade_levels.sl_pct}%</span>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );

    return (
        <div className="container mx-auto px-4 py-8 relative z-10">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-end mb-8 space-y-4 md:space-y-0">
                <div>
                    <h1 className="text-4xl font-bold text-white mb-2 flex items-center">
                        <Brain className="w-8 h-8 text-emerald-400 mr-3" />
                        ML Stock Screener
                    </h1>
                    <p className="text-white/50 text-sm">
                        Scanning {universeSize || '300'}+ NSE/BSE stocks · Top 5 highest probability only
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <div className="bg-[#1a1f36] p-1 rounded-xl inline-flex">
                        <button
                            onClick={() => { setActiveTab('swing'); setSelectedStock(null); }}
                            className={`px-4 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center ${activeTab === 'swing' ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/25' : 'text-white/50 hover:text-white'}`}
                        >
                            <TrendingUp className="w-4 h-4 mr-2" />
                            Swing 15%+
                        </button>
                        <button
                            onClick={() => { setActiveTab('intraday'); setSelectedStock(null); }}
                            className={`px-4 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center ${activeTab === 'intraday' ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/25' : 'text-white/50 hover:text-white'}`}
                        >
                            <Zap className="w-4 h-4 mr-2" />
                            Intraday 9%+
                        </button>
                    </div>
                    <button onClick={fetchData} className="p-2.5 text-white/30 hover:text-emerald-400 transition rounded-xl hover:bg-white/5 border border-white/10" title="Refresh">
                        {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <RefreshCw className="w-5 h-5" />}
                    </button>
                </div>
            </div>

            {loading ? (
                <div className="flex flex-col justify-center items-center py-32 space-y-4">
                    <div className="relative">
                        <div className="animate-spin rounded-full h-20 w-20 border-t-2 border-b-2 border-emerald-500"></div>
                        <Brain className="w-8 h-8 text-emerald-400 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
                    </div>
                    <p className="text-emerald-400 animate-pulse font-medium text-lg">Scanning all NSE & BSE stocks...</p>
                    <p className="text-white/30 text-sm text-center max-w-md">
                        Pre-filtering active movers → scoring with volume, EMA, RSI, MACD, VWAP, ADX → calculating entry, target & stop loss
                    </p>
                </div>
            ) : (
                <>
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                        {/* Left: Ranked Results — TOP 5 */}
                        <div className="lg:col-span-5 space-y-4">
                            <div className="flex items-center justify-between mb-1">
                                <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                                    <BarChart2 className="w-5 h-5 text-emerald-400" />
                                    {activeTab === 'swing' ? 'Swing Picks' : 'Intraday Picks'}
                                    <span className="text-xs text-white/30 font-normal bg-white/5 px-2 py-0.5 rounded-full">Top 5</span>
                                </h2>
                            </div>

                            {results.length === 0 ? (
                                <div className="text-center py-16 text-white/30 border border-dashed border-white/10 rounded-2xl bg-white/[0.02]">
                                    <Activity className="w-10 h-10 mx-auto mb-3 opacity-40" />
                                    <p className="font-medium">No high-probability setups found</p>
                                    <p className="text-xs mt-1">Markets may be closed. Check back during trading hours (9:15 AM - 3:30 PM IST).</p>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {results.map((stock, i) => renderStockCard(stock, i))}
                                </div>
                            )}
                        </div>

                        {/* Right: Deep Analysis Panel (Desktop only) */}
                        <div className="hidden lg:block lg:col-span-7 sticky top-24 self-start space-y-4">
                            {selectedStock ? (
                                <div className="bg-[#1a1f36]/80 p-6 rounded-2xl border border-emerald-500/20 shadow-2xl backdrop-blur-md">
                                    {/* Header */}
                                    <div className="flex items-center justify-between mb-5">
                                        <div>
                                            <h3
                                                onClick={() => { setActiveSymbol(selectedStock.symbol); if (onPageChange) onPageChange('demo'); }}
                                                className="text-3xl font-extrabold text-white hover:text-emerald-400 transition-colors cursor-pointer flex items-center gap-2 group/title"
                                            >
                                                {selectedStock.symbol}
                                                <ExternalLink className="w-4 h-4 opacity-0 group-hover/title:opacity-60 transition-opacity text-emerald-400" />
                                            </h3>
                                            <p className="text-sm text-white/50">{selectedStock.name} · {selectedStock.market}</p>
                                        </div>
                                        <div className="text-right">
                                            <div className={`text-4xl font-black ${selectedStock.probability >= 0.7 ? 'text-emerald-400' : selectedStock.probability >= 0.5 ? 'text-amber-400' : 'text-white/60'}`}>
                                                {(selectedStock.probability * 100).toFixed(1)}%
                                            </div>
                                            <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase border ${confidenceColor(selectedStock.confidence)}`}>
                                                {selectedStock.confidence}
                                            </span>
                                        </div>
                                    </div>

                                    {/* Probability bar */}
                                    <div className={`h-3 bg-white/5 rounded-full overflow-hidden mb-5 ${probBarGlow(selectedStock.probability)}`}>
                                        <div
                                            className={`h-full rounded-full transition-all duration-1000 ${probBarColor(selectedStock.probability)}`}
                                            style={{ width: `${selectedStock.probability * 100}%` }}
                                        />
                                    </div>

                                    {/* ===  ENTRY / TARGET / STOPLOSS  === */}
                                    {selectedStock.trade_levels && (
                                        <div className="grid grid-cols-3 gap-3 mb-5">
                                            <div className="bg-white/5 rounded-xl p-3.5 text-center border border-white/10">
                                                <div className="text-[10px] text-white/40 uppercase font-bold tracking-wider mb-1">Entry (CMP)</div>
                                                <div className="text-xl font-black text-white">₹{selectedStock.trade_levels.entry}</div>
                                            </div>
                                            <div className="bg-emerald-500/5 rounded-xl p-3.5 text-center border border-emerald-500/20">
                                                <div className="text-[10px] text-emerald-400/70 uppercase font-bold tracking-wider mb-1 flex items-center justify-center gap-1">
                                                    <Target className="w-3 h-3" /> Profit Target
                                                </div>
                                                <div className="text-xl font-black text-emerald-400">₹{selectedStock.trade_levels.target}</div>
                                                <div className="text-[10px] text-emerald-400/60 mt-0.5">+{selectedStock.trade_levels.target_pct}% upside</div>
                                            </div>
                                            <div className="bg-red-500/5 rounded-xl p-3.5 text-center border border-red-500/20">
                                                <div className="text-[10px] text-red-400/70 uppercase font-bold tracking-wider mb-1 flex items-center justify-center gap-1">
                                                    <ShieldAlert className="w-3 h-3" /> Stop Loss
                                                </div>
                                                <div className="text-xl font-black text-red-400">₹{selectedStock.trade_levels.stop_loss}</div>
                                                <div className="text-[10px] text-red-400/60 mt-0.5">-{selectedStock.trade_levels.sl_pct}% risk</div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Risk-Reward Badge */}
                                    {selectedStock.trade_levels && (
                                        <div className="flex items-center justify-center gap-3 mb-5 text-xs">
                                            <span className="bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 px-3 py-1.5 rounded-full font-bold">
                                                Risk:Reward → 1:{selectedStock.trade_levels.risk_reward}
                                            </span>
                                            <span className="text-white/30">|</span>
                                            <span className="text-white/40">
                                                Risk ₹{selectedStock.trade_levels.sl_pct}% to gain ₹{selectedStock.trade_levels.target_pct}%
                                            </span>
                                        </div>
                                    )}

                                    {/* Simple Summary */}
                                    <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-4 mb-5">
                                        <p className="text-xs text-emerald-300 font-bold uppercase tracking-widest mb-2 flex items-center">
                                            <BookOpen className="w-4 h-4 mr-2" />
                                            In Simple Words
                                        </p>
                                        <p className="text-sm text-white/80 leading-relaxed">
                                            {selectedStock.simple_summary}
                                        </p>
                                    </div>

                                    {/* Explain Mode Toggle */}
                                    <div className="flex items-center gap-2 mb-3">
                                        <button
                                            onClick={() => setExplainMode('simple')}
                                            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1 ${explainMode === 'simple' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'text-white/40 hover:text-white/60'}`}
                                        >
                                            <BookOpen className="w-3 h-3" /> Easy Mode
                                        </button>
                                        <button
                                            onClick={() => setExplainMode('technical')}
                                            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1 ${explainMode === 'technical' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'text-white/40 hover:text-white/60'}`}
                                        >
                                            <Wrench className="w-3 h-3" /> Technical
                                        </button>
                                    </div>

                                    {/* Key Quantitative Factors */}
                                    <div className="mb-5">
                                        <h4 className="text-xs text-white/50 font-bold uppercase tracking-widest mb-3 flex items-center">
                                            <Activity className="w-4 h-4 mr-2 text-emerald-400" />
                                            Key Indicators
                                        </h4>
                                        <div className="space-y-2">
                                            {(selectedStock.key_factors || []).map((factor: any, i: number) => {
                                                const isObj = typeof factor === 'object' && factor.technical;
                                                const text = isObj
                                                    ? (explainMode === 'simple' ? factor.simple : factor.technical)
                                                    : factor;
                                                return (
                                                    <div key={i} className="flex items-start gap-2.5 text-sm">
                                                        <span className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0 mt-1.5" />
                                                        <span className="text-white/80 leading-relaxed">{text}</span>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>

                                    {/* Why It Can Rise */}
                                    {selectedStock.why_it_can_rise && selectedStock.why_it_can_rise.length > 0 && (
                                        <div className="mb-5 bg-emerald-500/5 border border-emerald-500/15 rounded-xl p-4">
                                            <h4 className="text-xs text-emerald-400 font-bold uppercase tracking-widest mb-3 flex items-center">
                                                <ArrowUpRight className="w-4 h-4 mr-2" />
                                                Why This Stock Can Rise
                                            </h4>
                                            <div className="space-y-2.5">
                                                {selectedStock.why_it_can_rise.map((reason: any, i: number) => {
                                                    const isObj = typeof reason === 'object' && reason.technical;
                                                    const text = isObj
                                                        ? (explainMode === 'simple' ? reason.simple : reason.technical)
                                                        : reason;
                                                    return (
                                                        <div key={i} className="flex items-start gap-2.5 text-sm">
                                                            <span className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0 mt-1.5" />
                                                            <span className="text-white/70 leading-relaxed">{text}</span>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    )}

                                    {/* CTA */}
                                    <button
                                        onClick={() => {
                                            setActiveSymbol(selectedStock.symbol);
                                            if (onPageChange) onPageChange('demo');
                                        }}
                                        className="w-full bg-gradient-to-r from-emerald-600 to-emerald-400 hover:from-emerald-500 hover:to-emerald-300 text-white font-bold py-3.5 px-6 rounded-xl transition-all hover:scale-[1.02] active:scale-95 flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20"
                                    >
                                        <BarChart2 className="w-5 h-5" />
                                        View Live Chart & Demo Trade
                                    </button>
                                </div>
                            ) : (
                                <div className="text-center py-28 text-white/30 border border-dashed border-white/10 rounded-2xl bg-white/[0.02]">
                                    <Brain className="w-14 h-14 mx-auto mb-4 opacity-20" />
                                    <p className="text-lg font-medium text-white/40">Click a stock from the list</p>
                                    <p className="text-sm mt-1">to see entry, target, stop loss & full analysis</p>
                                </div>
                            )}

                            {/* Disclaimer */}
                            <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-4 flex items-start gap-3">
                                <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                                <div>
                                    <p className="text-xs text-amber-300/80 font-medium mb-1">⚠️ For Learning Only — NOT Financial Advice</p>
                                    <p className="text-[11px] text-white/40 leading-relaxed">
                                        {disclaimer || 'This screening tool is for educational purposes only. Entry, target, and stop loss levels are algorithmically calculated based on historical volatility and support/resistance — they are NOT guaranteed prices. Always do your own research before making any investment decisions.'}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </>
            )}

            {/* ── Mobile full-page detail view (at root level to escape stacking contexts) ── */}
            {selectedStock && (
                <div className="lg:hidden fixed inset-0 z-[100] bg-[#0d1117] flex flex-col">
                    {/* Fixed top bar - always visible */}
                    <div className="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-white/10 bg-[#0d1117]">
                        <div className="flex items-center gap-3">
                            <Brain className="w-5 h-5 text-emerald-400" />
                            <div>
                                <div className="text-sm font-black text-white uppercase tracking-tight">{selectedStock.symbol}</div>
                                <div className="text-[10px] text-white/40">{selectedStock.name} • {selectedStock.market || 'NSE'}</div>
                            </div>
                        </div>
                        <button
                            onClick={() => setSelectedStock(null)}
                            className="p-2.5 rounded-xl bg-white/10 hover:bg-white/20 text-white/70 hover:text-white transition-all active:scale-90"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    {/* Scrollable content */}
                    <div className="flex-1 overflow-y-auto p-5 space-y-5">
                        {/* Header with probability */}
                        <div className="flex items-center justify-between">
                            <div>
                                <h3
                                    onClick={() => { setActiveSymbol(selectedStock.symbol); if (onPageChange) onPageChange('demo'); }}
                                    className="text-2xl font-extrabold text-white hover:text-emerald-400 transition-colors cursor-pointer flex items-center gap-2"
                                >
                                    {selectedStock.symbol}
                                    <ExternalLink className="w-4 h-4 opacity-60 text-emerald-400" />
                                </h3>
                                <p className="text-xs text-white/50">{selectedStock.name} · {selectedStock.market}</p>
                            </div>
                            <div className="text-right">
                                <div className={`text-3xl font-black ${selectedStock.probability >= 0.7 ? 'text-emerald-400' : selectedStock.probability >= 0.5 ? 'text-amber-400' : 'text-white/60'}`}>
                                    {(selectedStock.probability * 100).toFixed(1)}%
                                </div>
                                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${confidenceColor(selectedStock.confidence)}`}>
                                    {selectedStock.confidence}
                                </span>
                            </div>
                        </div>

                        {/* Trade Levels */}
                        {selectedStock.trade_levels && (
                            <div className="grid grid-cols-3 gap-2">
                                <div className="bg-white/5 rounded-xl p-3 text-center border border-white/10">
                                    <div className="text-[9px] text-white/40 uppercase font-bold mb-1">Entry</div>
                                    <div className="text-lg font-black text-white">₹{selectedStock.trade_levels.entry}</div>
                                </div>
                                <div className="bg-emerald-500/5 rounded-xl p-3 text-center border border-emerald-500/20">
                                    <div className="text-[9px] text-emerald-400/70 uppercase font-bold mb-1">Target</div>
                                    <div className="text-lg font-black text-emerald-400">₹{selectedStock.trade_levels.target}</div>
                                    <div className="text-[9px] text-emerald-400/60">+{selectedStock.trade_levels.target_pct}%</div>
                                </div>
                                <div className="bg-red-500/5 rounded-xl p-3 text-center border border-red-500/20">
                                    <div className="text-[9px] text-red-400/70 uppercase font-bold mb-1">Stop Loss</div>
                                    <div className="text-lg font-black text-red-400">₹{selectedStock.trade_levels.stop_loss}</div>
                                    <div className="text-[9px] text-red-400/60">-{selectedStock.trade_levels.sl_pct}%</div>
                                </div>
                            </div>
                        )}

                        {/* Simple Summary */}
                        <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-4">
                            <p className="text-xs text-emerald-300 font-bold uppercase tracking-widest mb-2 flex items-center">
                                <BookOpen className="w-4 h-4 mr-2" /> In Simple Words
                            </p>
                            <p className="text-sm text-white/80 leading-relaxed">{selectedStock.simple_summary}</p>
                        </div>

                        {/* Key Factors */}
                        <div>
                            <h4 className="text-xs text-white/50 font-bold uppercase tracking-widest mb-3 flex items-center">
                                <Activity className="w-4 h-4 mr-2 text-emerald-400" /> Key Indicators
                            </h4>
                            <div className="space-y-2">
                                {(selectedStock.key_factors || []).map((factor: any, i: number) => {
                                    const isObj = typeof factor === 'object' && factor.technical;
                                    const text = isObj ? (explainMode === 'simple' ? factor.simple : factor.technical) : factor;
                                    return (
                                        <div key={i} className="flex items-start gap-2.5 text-sm">
                                            <span className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0 mt-1.5" />
                                            <span className="text-white/80 leading-relaxed">{text}</span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {/* CTA */}
                        <button
                            onClick={() => {
                                setActiveSymbol(selectedStock.symbol);
                                if (onPageChange) onPageChange('demo');
                            }}
                            className="w-full bg-gradient-to-r from-emerald-600 to-emerald-400 text-white font-bold py-3.5 px-6 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20"
                        >
                            <BarChart2 className="w-5 h-5" /> View Chart & Trade
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
