import { useEffect, useState, useCallback } from 'react';
import {
    Brain, Zap, TrendingUp, RefreshCw, Loader2, AlertTriangle,
    Target, ShieldAlert, BookOpen, Wrench, ChevronDown,
    BarChart2, Activity, CheckCircle2,
    XCircle, Clock, Layers, Sigma, ExternalLink, X, Database, Building2
} from 'lucide-react';
import { useDemoStore } from '../store/demoStore';
import { motion, AnimatePresence } from 'framer-motion';
import { SignalExplorer } from '../features/signals/components/SignalExplorer';
import { CompanyIntelPanel } from '../features/docintel/components/CompanyIntelPanel';

/* ─── Types ─────────────────────────────────────────────────────── */
interface Signal {
    name: string;
    tech: string;
    simple: string;
}

interface TradeLevels {
    entry: number;
    target: number;
    partial_target: number;
    stop_loss: number;
    target_pct: number;
    partial_pct: number;
    sl_pct: number;
    risk_reward: number;
    pivot_r1: number;
    pivot_s1: number;
    fib_382: number;
    fib_618: number;
    avwap: number;
}

interface StockResult {
    symbol: string;
    name: string;
    market: string;
    category?: string;
    probability: number;
    confidence: 'HIGH' | 'MEDIUM' | 'LOW';
    confluence: string;
    simple_summary: string;
    trade_levels: TradeLevels;
    bullish_signals: Signal[];
    bearish_signals: Signal[];
    metrics: {
        cmp: number;
        volume_ratio: number;
        rsi: number;
        ema_alignment: number;
        adx: number;
        atr_pct: number;
        cmf: number;
        mfi: number;
        obv_trend: number;
        supertrend: string;
        ichimoku: string;
        close_strength?: number;
        narrow_range?: string;
        bb_squeeze?: string;
        rs_ranking?: number;
        stage?: number;
        pocket_pivot?: boolean;
        vcp?: boolean;
        acc_intensity?: number;
        force_index?: number;
        tight_close?: number;
    };
}

interface ScreenerResponse {
    mode: string;
    for_date?: string;
    generated_at: string;
    model_version: string;
    universe_scanned: number;
    indicators_used: number;
    results: StockResult[];
    disclaimer: string;
}

interface TradingSuggestionPageProps {
    onPageChange?: (page: any) => void;
}

/* ─── Helpers ────────────────────────────────────────────────────── */
const conf = (c: string) => ({
    HIGH: 'text-[#22c55e] bg-[#22c55e]/10 border-[#22c55e]/30',
    MEDIUM: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
    LOW: 'text-slate-400 bg-slate-500/10 border-slate-500/30',
} as any)[c] ?? 'text-white/40';

const probColor = (p: number) =>
    p >= 0.75 ? '#22c55e' : p >= 0.60 ? '#fbbf24' : '#94a3b8';

const probBar = (p: number) =>
    p >= 0.75 ? 'from-[#22c55e] to-emerald-400'
        : p >= 0.60 ? 'from-amber-600 to-amber-400'
            : 'from-slate-600 to-slate-400';

/* ─── Signal Badge ───────────────────────────────────────────────── */
function SignalBadge({ sig, mode }: { sig: Signal; mode: 'simple' | 'technical'; }) {
    const [open, setOpen] = useState(false);
    return (
        <motion.button
            initial={false}
            onClick={() => setOpen(o => !o)}
            className="w-full text-left flex items-start gap-2 p-3 rounded-xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.04] hover:border-[#22c55e]/30 transition-all overflow-hidden"
        >
            <CheckCircle2 className="w-4 h-4 text-[#22c55e] flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
                <div className="flex justify-between items-start gap-2">
                    <span className="text-[11px] font-bold text-[#22c55e] uppercase tracking-wider">{sig.name}</span>
                    <motion.div animate={{ rotate: open ? 180 : 0 }}>
                        <ChevronDown className="w-3 h-3 text-white/30" />
                    </motion.div>
                </div>
                <p className="text-xs text-white/70 leading-relaxed mt-1 font-light">
                    {mode === 'simple' ? sig.simple : sig.tech}
                </p>
                <AnimatePresence>
                    {open && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                        >
                            <p className="text-[10px] text-white/40 mt-2 font-mono pt-2 border-t border-white/5">
                                {mode === 'simple' ? sig.tech : sig.simple}
                            </p>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </motion.button>
    );
}

function BearishBadge({ sig, mode }: { sig: Signal; mode: 'simple' | 'technical'; }) {
    return (
        <div className="flex items-start gap-2 p-3 rounded-xl bg-red-500/5 border border-red-500/10">
            <XCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
                <span className="text-[11px] font-bold text-red-400 uppercase tracking-wider">{sig.name}</span>
                <p className="text-[11px] text-white/50 leading-relaxed mt-1 font-light">
                    {mode === 'simple' ? sig.simple : sig.tech}
                </p>
            </div>
        </div>
    );
}

/* ─── Stock card (list) ──────────────────────────────────────────── */
function StockCard({ stock, rank, selected, onClick, onNavigate }: {
    stock: StockResult; rank: number; selected: boolean; onClick: () => void; onNavigate: () => void;
}) {
    const [bullish, total] = (stock.confluence || '0/0').split('/').map(Number);
    return (
        <motion.button
            whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }}
            onClick={onClick} className={`w-full text-left p-4 rounded-2xl border transition-all duration-300 relative overflow-hidden group
            ${selected
                    ? 'bg-white/[0.05] border-white/20 shadow-lg'
                    : 'bg-white/[0.01] border-white/5 hover:border-white/10'}`}
        >
            {selected && <div className="absolute inset-0 bg-gradient-to-r from-white/[0.02] to-transparent pointer-events-none" />}
            <div className="relative z-10 flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center font-black text-sm
                        ${rank === 1 ? 'bg-amber-500/20 text-amber-400' : rank === 2 ? 'bg-slate-400/20 text-slate-300' : 'bg-white/5 text-white/30'}`}>
                        {rank}
                    </div>
                    <div>
                        <div
                            onClick={(e) => { e.stopPropagation(); onNavigate(); }}
                            className="font-black text-lg text-white tracking-tight hover:text-[#22c55e] transition-colors cursor-pointer flex items-center gap-1.5 group/sym"
                        >
                            {stock.symbol}
                            <ExternalLink className="w-3 h-3 opacity-0 group-hover/sym:opacity-60 transition-opacity text-[#22c55e]" />
                        </div>
                        <div className="text-[10px] text-white/40 truncate max-w-[140px] font-light">{stock.name}</div>
                        {stock.category && <div className="text-[8px] text-[#22c55e]/80 bg-[#22c55e]/10 px-1.5 py-0.5 rounded-full mt-1 inline-block uppercase font-bold tracking-wider">{stock.category}</div>}
                    </div>
                </div>
                <div className="text-right">
                    <div className="text-xl font-black tracking-tighter" style={{ color: probColor(stock.probability || 0) }}>
                        {((stock.probability || 0) * 100).toFixed(0)}%
                    </div>
                    <span className={`text-[9px] font-black px-2 py-0.5 rounded-full border uppercase tracking-widest ${conf(stock.confidence || 'LOW')}`}>
                        {stock.confidence || '-'}
                    </span>
                </div>
            </div>

            {/* Confluence bar */}
            <div className="mb-3 relative z-10">
                <div className="flex justify-between text-[9px] text-white/40 mb-1.5 font-bold uppercase tracking-wider">
                    <span>Signals: {bullish}/{total}</span>
                    <span>{total > 0 ? ((bullish / total) * 100).toFixed(0) : '0'}%</span>
                </div>
                <div className={`h-1.5 bg-black/50 rounded-full overflow-hidden border border-white/5`}>
                    <motion.div
                        initial={{ width: 0 }} animate={{ width: `${(stock.probability || 0) * 100}%` }} transition={{ duration: 1, ease: 'easeOut' }}
                        className={`h-full rounded-full bg-gradient-to-r ${probBar(stock.probability || 0)} shadow-[0_0_10px_rgba(34,197,94,0.5)]`}
                    />
                </div>
            </div>

            {/* Trade levels */}
            {stock.trade_levels && (
                <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-white/5 relative z-10">
                    <div className="text-center bg-black/40 rounded-lg py-1.5">
                        <div className="text-[8px] text-white/30 uppercase font-bold tracking-widest">Entry</div>
                        <div className="text-xs font-black text-white">₹{stock.trade_levels.entry}</div>
                    </div>
                    <div className="text-center bg-[#22c55e]/5 rounded-lg py-1.5 border border-[#22c55e]/10">
                        <div className="text-[8px] text-[#22c55e]/60 uppercase font-bold tracking-widest">Target</div>
                        <div className="text-xs font-black text-[#22c55e]">+{stock.trade_levels.target_pct}%</div>
                    </div>
                    <div className="text-center bg-red-500/5 rounded-lg py-1.5 border border-red-500/10">
                        <div className="text-[8px] text-red-500/60 uppercase font-bold tracking-widest">SL</div>
                        <div className="text-xs font-black text-red-500">-{stock.trade_levels.sl_pct}%</div>
                    </div>
                </div>
            )}
        </motion.button>
    );
}

/* ─── Full detail panel ──────────────────────────────────────────── */
function DetailPanel({ stock, mode, onExplainToggle, onTrade }: {
    stock: StockResult;
    mode: 'simple' | 'technical';
    onExplainToggle: () => void;
    onTrade: () => void;
}) {
    const tl = stock.trade_levels;
    const [bullish, total] = (stock.confluence || '0/0').split('/').map(Number);
    const bullishSignals = stock.bullish_signals || [];
    const bearishSignals = stock.bearish_signals || [];
    const m = stock.metrics || {} as any;

    return (
        <motion.div
            initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ type: 'spring', damping: 20 }}
            className="bg-[#0a0a0a] rounded-3xl lg:border border-white/10 overflow-hidden shadow-2xl relative"
        >
            {/* Top glowing orb */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-[#22c55e]/10 blur-[100px] rounded-full pointer-events-none" />

            {/* ── Top strip ── */}
            <div className="px-4 py-4 lg:px-6 lg:py-6 border-b border-white/5 relative z-10">
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-3">
                            <h2 onClick={onTrade} className="text-2xl lg:text-4xl font-black text-white tracking-tighter hover:text-[#22c55e] transition-colors cursor-pointer flex items-center gap-2 group/title">
                                {stock.symbol}
                                <ExternalLink className="w-4 h-4 lg:w-5 lg:h-5 opacity-0 group-hover/title:opacity-60 transition-opacity text-[#22c55e]" />
                            </h2>
                            <span className={`px-2.5 py-1 rounded-full text-[10px] font-black border uppercase tracking-widest ${conf(stock.confidence)}`}>
                                {stock.confidence}
                            </span>
                        </div>
                        <p className="text-xs lg:text-sm text-white/40 mt-1 font-light">{stock.name} • <span className="text-white/60 font-semibold">{stock.market}</span></p>
                    </div>
                    <div className="text-right">
                        <div className="text-3xl lg:text-5xl font-black tracking-tighter" style={{ color: probColor(stock.probability || 0), textShadow: '0 0 10px rgba(0,0,0,0.5)' }}>
                            {((stock.probability || 0) * 100).toFixed(1)}%
                        </div>
                        <div className="text-[10px] text-white/40 uppercase tracking-widest font-bold">{bullish}/{total} Score</div>
                    </div>
                </div>

                <div className="flex items-center gap-2 mt-6">
                    <button onClick={onExplainToggle}
                        className={`flex-1 py-2.5 rounded-xl text-xs font-bold uppercase tracking-widest flex items-center justify-center gap-2 transition-all border
                            ${mode === 'simple' ? 'bg-white/10 text-white border-white/20' : 'bg-transparent text-white/40 border-white/5 hover:border-white/10 hover:text-white'}`}>
                        <BookOpen className="w-4 h-4" /> Plain English
                    </button>
                    <button onClick={onExplainToggle}
                        className={`flex-1 py-2.5 rounded-xl text-xs font-bold uppercase tracking-widest flex items-center justify-center gap-2 transition-all border
                            ${mode === 'technical' ? 'bg-white/10 text-white border-white/20' : 'bg-transparent text-white/40 border-white/5 hover:border-white/10 hover:text-white'}`}>
                        <Wrench className="w-4 h-4" /> Raw Data
                    </button>
                </div>
            </div>

            <div className="overflow-y-auto lg:max-h-[calc(100vh-320px)] custom-scrollbar relative z-10">
                {/* ── Simple summary ── */}
                <div className="px-4 py-4 lg:px-6 lg:py-5 border-b border-white/5 bg-white/[0.01]">
                    <div className="flex items-center gap-2 mb-3">
                        <Brain className="w-4 h-4 text-[#22c55e]" />
                        <span className="text-[10px] text-[#22c55e] font-bold uppercase tracking-widest">AI Synopsis</span>
                    </div>
                    <p className="text-sm text-white/70 leading-relaxed font-light">{stock.simple_summary}</p>
                </div>

                {/* ── Trade levels ── */}
                {tl && (
                    <div className="p-4 lg:p-6 border-b border-white/5">
                        <div className="flex items-center gap-2 mb-4">
                            <Target className="w-4 h-4 text-white/60" />
                            <h3 className="text-xs font-bold text-white/60 uppercase tracking-widest">Action Plan</h3>
                        </div>

                        <div className="grid grid-cols-3 gap-2 lg:gap-3 mb-4">
                            <div className="bg-white/[0.03] rounded-xl lg:rounded-2xl p-3 lg:p-4 text-center border border-white/5">
                                <div className="text-[8px] lg:text-[9px] text-white/40 uppercase font-bold tracking-widest mb-1">Entry</div>
                                <div className="text-lg lg:text-2xl font-black text-white">₹{tl.entry}</div>
                            </div>
                            <div className="bg-[#22c55e]/10 rounded-xl lg:rounded-2xl p-3 lg:p-4 text-center border border-[#22c55e]/20 relative overflow-hidden">
                                <div className="absolute inset-0 bg-gradient-to-t from-[#22c55e]/10 to-transparent pointer-events-none" />
                                <div className="text-[8px] lg:text-[9px] text-[#22c55e] uppercase font-bold tracking-widest mb-1">Target</div>
                                <div className="text-lg lg:text-2xl font-black text-[#22c55e]">₹{tl.target}</div>
                                <div className="text-[9px] lg:text-[10px] text-[#22c55e]/70 font-bold">+{tl.target_pct}%</div>
                            </div>
                            <div className="bg-red-500/5 rounded-xl lg:rounded-2xl p-3 lg:p-4 text-center border border-red-500/10">
                                <div className="text-[8px] lg:text-[9px] text-red-500/70 uppercase font-bold tracking-widest mb-1">Stop Loss</div>
                                <div className="text-lg lg:text-2xl font-black text-red-500">₹{tl.stop_loss}</div>
                                <div className="text-[9px] lg:text-[10px] text-red-500/70 font-bold">-{tl.sl_pct}%</div>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-2 lg:gap-3 mb-4">
                            <div className="bg-sky-500/5 rounded-xl lg:rounded-2xl p-2.5 lg:p-3 text-center border border-sky-500/10 flex items-center justify-between px-3 lg:px-5">
                                <div className="text-left">
                                    <div className="text-[8px] lg:text-[9px] text-sky-400 uppercase font-bold tracking-widest mb-0.5">Book 50% At</div>
                                    <div className="text-[9px] lg:text-[10px] text-sky-400/60 font-medium">+{tl.partial_pct}%</div>
                                </div>
                                <div className="text-base lg:text-xl font-black text-sky-400">₹{tl.partial_target}</div>
                            </div>
                            <div className="bg-white/[0.02] rounded-xl lg:rounded-2xl p-2.5 lg:p-3 text-center border border-white/5 flex items-center justify-between px-3 lg:px-5">
                                <div className="text-left">
                                    <div className="text-[8px] lg:text-[9px] text-white/50 uppercase font-bold tracking-widest mb-0.5">Risk Form</div>
                                    <div className="text-[9px] lg:text-[10px] text-white/40 font-medium">{tl.sl_pct}% vs {tl.target_pct}%</div>
                                </div>
                                <div className="text-base lg:text-xl font-black text-white">1 : {tl.risk_reward}</div>
                            </div>
                        </div>

                        {mode === 'simple' && (
                            <div className="mt-2 p-4 bg-white/[0.02] rounded-2xl border border-white/5 text-xs text-white/50 leading-relaxed font-light">
                                <strong className="text-white/80 font-semibold">Playbook:</strong> Buy at ₹{tl.entry}.
                                Once the stock hits ₹{tl.partial_target}, sell half your position to secure profits.
                                Let the rest ride to ₹{tl.target}. Keep a strict stop loss at ₹{tl.stop_loss}.
                            </div>
                        )}
                    </div>
                )}

                {/* ── Bullish signals ── */}
                <div className="px-4 py-4 lg:px-6 lg:py-5 border-b border-white/5">
                    <div className="flex items-center gap-2 mb-4">
                        <TrendingUp className="w-4 h-4 text-[#22c55e]" />
                        <h3 className="text-xs font-bold text-[#22c55e] uppercase tracking-widest">
                            Bullish Confluence ({bullishSignals.length})
                        </h3>
                    </div>
                    <div className="space-y-2">
                        {bullishSignals.map((s, i) => (
                            <SignalBadge key={i} sig={s} mode={mode} />
                        ))}
                    </div>
                </div>

                {/* ── Bearish/Caution signals ── */}
                {bearishSignals.length > 0 && (
                    <div className="px-4 py-4 lg:px-6 lg:py-5 border-b border-white/5 bg-white/[0.01]">
                        <div className="flex items-center gap-2 mb-4">
                            <ShieldAlert className="w-4 h-4 text-red-500/70" />
                            <h3 className="text-xs font-bold text-red-500/70 uppercase tracking-widest">
                                Drag Factors ({bearishSignals.length})
                            </h3>
                        </div>
                        <div className="space-y-2">
                            {bearishSignals.slice(0, 4).map((s, i) => (
                                <BearishBadge key={i} sig={s} mode={mode} />
                            ))}
                        </div>
                    </div>
                )}

                {/* ── Metrics grid ── */}
                <div className="px-4 py-4 lg:px-6 lg:py-6 border-b border-white/5">
                    <div className="flex items-center gap-2 mb-5">
                        <Activity className="w-4 h-4 text-white/40" />
                        <h3 className="text-xs font-bold text-white/40 uppercase tracking-widest">Raw Core Metrics</h3>
                    </div>
                    <div className="grid grid-cols-3 lg:grid-cols-4 gap-2 lg:gap-3">
                        {[
                            { label: 'Close Price', val: `₹${m.cmp || 0}`, sub: '', color: 'text-white' },
                            { label: 'Close Str.', val: `${m.close_strength || 0}%`, sub: (m.close_strength || 0) > 70 ? 'Near high' : 'Weak', color: (m.close_strength || 0) > 70 ? 'text-[#22c55e]' : 'text-white/50' },
                            { label: 'Volume', val: `${m.volume_ratio || 0}x`, sub: 'vs 20d avg', color: (m.volume_ratio || 0) > 1.5 ? 'text-[#22c55e]' : 'text-white/60' },
                            { label: 'RS Rank', val: `${m.rs_ranking?.toFixed(1) || '-'}x`, sub: 'vs Nifty 50', color: (m.rs_ranking || 0) > 1.5 ? 'text-amber-400' : (m.rs_ranking || 0) > 1 ? 'text-[#22c55e]' : 'text-white/50' },
                            { label: 'Stage', val: ['-', 'Base', 'ADV', 'Top', 'Down'][m.stage || 0], sub: 'Weinstein', color: m.stage === 2 ? 'text-[#22c55e]' : m.stage === 4 ? 'text-red-500' : 'text-white/50' },
                            { label: 'Pocket Pivot', val: m.pocket_pivot ? 'YES' : '-', sub: 'Stealth buying', color: m.pocket_pivot ? 'text-[#22c55e]' : 'text-white/30' },
                            { label: 'VCP', val: m.vcp ? 'YES' : '-', sub: 'Minervini', color: m.vcp ? 'text-amber-400' : 'text-white/30' },
                            { label: 'Accum.', val: `${m.acc_intensity?.toFixed(1) || '0'}`, sub: (m.acc_intensity || 0) > 0.3 ? 'Active' : 'Neutral', color: (m.acc_intensity || 0) > 0.3 ? 'text-[#22c55e]' : 'text-white/50' },
                            { label: 'Force Idx', val: `${m.force_index?.toFixed(1) || '0'}M`, sub: (m.force_index || 0) > 0 ? 'Buying' : 'Selling', color: (m.force_index || 0) > 0 ? 'text-[#22c55e]' : 'text-red-500' },
                            { label: 'Tight Close', val: `${m.tight_close || 0}d`, sub: (m.tight_close || 0) >= 3 ? 'Pattern' : '', color: (m.tight_close || 0) >= 3 ? 'text-amber-400' : 'text-white/50' },
                            { label: 'NR Pattern', val: m.narrow_range || 'Normal', sub: m.narrow_range === 'NR7' ? 'Expansion' : '', color: (m.narrow_range === 'NR7' || m.narrow_range === 'NR4') ? 'text-amber-400' : 'text-white/50' },
                            { label: 'Supertrend', val: m.supertrend || '-', sub: '', color: m.supertrend === 'BUY' ? 'text-[#22c55e]' : 'text-red-500' },
                        ].map((m, i) => (
                            <div key={i} className="bg-white/[0.02] rounded-xl p-3 border border-white/5 text-center flex flex-col justify-center">
                                <div className="text-[8px] text-white/30 uppercase font-bold tracking-widest mb-1">{m.label}</div>
                                <div className={`text-sm font-black tracking-tight ${m.color}`}>{m.val}</div>
                                {m.sub && <div className="text-[8px] text-white/20 mt-0.5">{m.sub}</div>}
                            </div>
                        ))}
                    </div>
                </div>

                <div className="p-4 lg:p-6">
                    <motion.button
                        whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                        onClick={onTrade}
                        className="w-full bg-white text-black font-black py-5 rounded-2xl transition-all flex items-center justify-center gap-2 hover:bg-gray-200 text-lg uppercase tracking-wider"
                    >
                        <BarChart2 className="w-5 h-5" />
                        Execute in Terminal
                    </motion.button>
                </div>
            </div>
        </motion.div>
    );
}

/* ──────────────────────────────────────────────────────────────────
   MAIN PAGE
────────────────────────────────────────────────────────────────── */
export function TradingSuggestionPage({ onPageChange }: TradingSuggestionPageProps) {
    const [intradayData, setIntradayData] = useState<ScreenerResponse | null>(null);
    const [swingData, setSwingData] = useState<ScreenerResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState<'swing' | 'intraday' | 'registry' | 'intel'>('swing');
    const [selected, setSelected] = useState<StockResult | null>(null);
    const [explainMode, setExplainMode] = useState<'simple' | 'technical'>('simple');
    const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
    const [forDate, setForDate] = useState<string>('');
    const { setActiveSymbol } = useDemoStore();

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 8000);
            const res = await fetch('/api/news', { signal: controller.signal });
            clearTimeout(timeout);
            const data = await res.json();

            setForDate(data.for_date || '');
            const makeResponse = (results: StockResult[], mode: string): ScreenerResponse => ({
                mode,
                for_date: data.for_date,
                generated_at: new Date().toISOString(),
                model_version: data.model_version || '5.0.0',
                universe_scanned: data.universe_scanned || 0,
                indicators_used: data.indicators_used || 16,
                results,
                disclaimer: data.disclaimer || '',
            });

            setIntradayData(makeResponse(data.intradaySetups || [], 'intraday'));
            setSwingData(makeResponse(data.swingSetups || [], 'swing'));
            setLastRefresh(new Date());

            const top = (data.swingSetups || data.intradaySetups || [])[0];
            if (top) setSelected(top);
        } catch (e) {
            console.error('[TradingSuggestionPage] fetch failed:', e);
            // Always initialize so the page shows the empty state, not a blank screen
            const empty = (mode: string): ScreenerResponse => ({
                mode, for_date: '', generated_at: new Date().toISOString(),
                model_version: '5.0.0', universe_scanned: 0, indicators_used: 0,
                results: [], disclaimer: ''
            });
            setIntradayData(empty('intraday'));
            setSwingData(empty('swing'));
        }
        setLoading(false);
    }, []);

    useEffect(() => { fetchData(); }, [fetchData]);

    const activeData = activeTab === 'swing' ? swingData : intradayData;
    const results = activeData?.results || [];

    useEffect(() => {
        const isDesktop = window.innerWidth >= 1024;
        if (results.length > 0 && isDesktop && (!selected || !results.find(r => r.symbol === selected?.symbol))) {
            setSelected(results[0]);
        } else if (!isDesktop) {
            // On mobile, never auto-open — always show the stock list first
            setSelected(null);
        }
    }, [activeTab, results]);

    return (
        <div className="min-h-screen bg-[#050505] font-sans selection:bg-[#22c55e]/30">

            {/* ── Background Elements ── */}
            <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
                <div className="absolute top-0 right-1/4 w-[40vw] h-[40vw] bg-white/[0.01] blur-[120px] rounded-full mix-blend-screen" />
                <div className="absolute bottom-0 left-1/4 w-[30vw] h-[30vw] bg-white/[0.01] blur-[100px] rounded-full mix-blend-screen" />
                <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.15] mix-blend-overlay pointer-events-none" />
            </div>

            {/* ── Header Top bar ── */}
            <div className="relative z-20 border-b border-white/5 bg-[#050505]/80 backdrop-blur-xl">
                <div className="container mx-auto px-6 py-5 flex flex-wrap items-center justify-between gap-6">
                    <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-2xl bg-white/[0.03] border border-white/10 flex items-center justify-center">
                            <Brain className="w-6 h-6 text-[#22c55e]" />
                        </div>
                        <div>
                            <h1 className="text-2xl font-black text-white tracking-tight uppercase">Trading Suggestions</h1>
                            <div className="flex items-center gap-3 mt-1.5">
                                {forDate && <span className="text-[10px] text-black font-black uppercase tracking-widest bg-[#22c55e] px-2 py-0.5 rounded-sm">For {forDate}</span>}
                                <p className="text-[10px] text-white/40 uppercase tracking-widest font-bold">
                                    V{activeData?.model_version} • {activeData?.universe_scanned} stocks scanned
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-4">
                        <div className="bg-white/[0.02] p-1.5 rounded-2xl flex border border-white/5">
                            <button onClick={() => setActiveTab('swing')}
                                className={`px-6 py-2.5 rounded-xl text-xs uppercase tracking-widest font-bold flex items-center gap-2 transition-all
                                    ${activeTab === 'swing' ? 'bg-white text-black' : 'text-white/40 hover:text-white hover:bg-white/5'}`}>
                                <TrendingUp className="w-4 h-4" /> Swing
                            </button>
                            <button onClick={() => setActiveTab('intraday')}
                                className={`px-6 py-2.5 rounded-xl text-xs uppercase tracking-widest font-bold flex items-center gap-2 transition-all
                                    ${activeTab === 'intraday' ? 'bg-white text-black' : 'text-white/40 hover:text-white hover:bg-white/5'}`}>
                                <Zap className="w-4 h-4" /> Intraday
                            </button>
                            <button onClick={() => setActiveTab('registry')}
                                className={`px-6 py-2.5 rounded-xl text-xs uppercase tracking-widest font-bold flex items-center gap-2 transition-all
                                    ${activeTab === 'registry' ? 'bg-white text-black' : 'text-white/40 hover:text-white hover:bg-white/5'}`}>
                                <Database className="w-4 h-4" /> Registry
                            </button>
                            <button onClick={() => setActiveTab('intel')}
                                className={`px-6 py-2.5 rounded-xl text-xs uppercase tracking-widest font-bold flex items-center gap-2 transition-all
                                    ${activeTab === 'intel' ? 'bg-white text-black' : 'text-white/40 hover:text-white hover:bg-white/5'}`}>
                                <Building2 className="w-4 h-4" /> Intel
                            </button>
                        </div>

                        <button onClick={fetchData}
                            className="p-3.5 rounded-2xl border border-white/10 text-white/40 hover:text-[#22c55e] hover:border-[#22c55e]/50 hover:bg-[#22c55e]/10 transition-all">
                            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <RefreshCw className="w-5 h-5" />}
                        </button>
                    </div>
                </div>
            </div>

            {/* ── Body ── */}
            <div className="relative z-10 container mx-auto px-6 py-8">
                {loading ? (
                    <div className="flex flex-col items-center justify-center py-40 space-y-6">
                        <div className="relative">
                            <div className="w-32 h-32 rounded-full border-2 border-t-white/80 border-r-white/20 border-b-transparent border-l-transparent animate-spin" />
                            <div className="absolute inset-0 bg-white/5 blur-[30px] rounded-full animate-pulse" />
                            <Brain className="w-10 h-10 text-white/80 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
                        </div>
                        <p className="text-white/80 font-black uppercase tracking-widest text-lg animate-pulse">Running Alpha Engine...</p>
                        <div className="text-center text-white/20 text-xs font-mono tracking-widest space-y-2">
                            <p>Loading market depth...</p>
                            <p>Calculating institutional footprints...</p>
                            <p>Scanning 21,500+ securities...</p>
                        </div>
                    </div>
                ) : activeTab === 'registry' ? (
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                        <SignalExplorer />
                    </motion.div>
                ) : activeTab === 'intel' ? (
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                        <CompanyIntelPanel />
                    </motion.div>
                ) : results.length === 0 ? (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center justify-center py-40 border border-dashed border-white/5 rounded-3xl bg-white/[0.01]">
                        <Activity className="w-16 h-16 text-white/10 mb-6" />
                        <p className="text-white/40 font-bold text-xl tracking-tight">No high-probability setups found.</p>
                        <p className="text-white/20 text-sm mt-2 max-w-md text-center font-light">The engine requires rigorous parameters. If there are no trades, preservation of capital is the priority. Check back after market close.</p>
                    </motion.div>
                ) : (
                    <>
                        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">

                            {/* ── Left list ── */}
                            <div className="lg:col-span-4 space-y-4">
                                {/* Stat bar */}
                                <div className="grid grid-cols-3 gap-3 mb-2">
                                    {[
                                        { label: 'Signals', val: activeData?.indicators_used || 20, icon: Layers },
                                        { label: 'Scanned', val: `${activeData?.universe_scanned}+`, icon: Sigma },
                                        { label: 'Matches', val: results.length, icon: CheckCircle2 },
                                    ].map(({ label, val, icon: Icon }) => (
                                        <div key={label} className="bg-white/[0.02] rounded-2xl p-3 text-center border border-white/5">
                                            <Icon className="w-4 h-4 text-[#22c55e] mx-auto mb-2 opacity-80" />
                                            <div className="text-lg font-black text-white">{val}</div>
                                            <div className="text-[9px] text-white/30 uppercase tracking-widest font-bold mt-0.5">{label}</div>
                                        </div>
                                    ))}
                                </div>

                                <div className="space-y-3">
                                    {results.map((s, i) => (
                                        <motion.div key={s.symbol} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                                            <StockCard
                                                stock={s} rank={i + 1}
                                                selected={selected?.symbol === s.symbol}
                                                onClick={() => setSelected(s)}
                                                onNavigate={() => {
                                                    setActiveSymbol(s.symbol);
                                                    if (onPageChange) onPageChange('demo');
                                                }}
                                            />
                                        </motion.div>
                                    ))}
                                </div>

                                {lastRefresh && (
                                    <div className="flex items-center gap-2 text-[10px] text-white/20 px-2 uppercase tracking-widest font-bold pt-4">
                                        <Clock className="w-3 h-3" />
                                        Scan accurate as of {lastRefresh.toLocaleTimeString('en-IN')}
                                    </div>
                                )}
                            </div>

                            {/* ── Right detail (Desktop: inline, Mobile: overlay modal) ── */}
                            <div className="hidden lg:block lg:col-span-8 sticky top-[160px]">
                                <AnimatePresence mode="popLayout">
                                    {selected ? (
                                        <motion.div key={selected.symbol} initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.98 }} transition={{ duration: 0.2 }}>
                                            <DetailPanel
                                                stock={selected}
                                                mode={explainMode}
                                                onExplainToggle={() => setExplainMode(m => m === 'simple' ? 'technical' : 'simple')}
                                                onTrade={() => {
                                                    setActiveSymbol(selected.symbol);
                                                    if (onPageChange) onPageChange('demo');
                                                }}
                                            />
                                        </motion.div>
                                    ) : (
                                        <div className="flex flex-col items-center justify-center py-40 border border-dashed border-white/5 rounded-3xl">
                                            <Brain className="w-12 h-12 text-white/5 mb-4" />
                                            <p className="text-white/20 uppercase tracking-widest font-bold text-xs">Select a stock to view thesis</p>
                                        </div>
                                    )}
                                </AnimatePresence>

                                {/* Disclaimer */}
                                <div className="mt-6 bg-white/[0.01] border border-white/5 rounded-2xl p-5 flex gap-4 backdrop-blur-sm">
                                    <AlertTriangle className="w-5 h-5 text-white/30 flex-shrink-0 mt-0.5" />
                                    <div>
                                        <p className="text-[10px] text-white/50 uppercase tracking-widest font-bold mb-1.5">Simulation Data Only</p>
                                        <p className="text-[11px] text-white/30 leading-relaxed font-light">
                                            {activeData?.disclaimer}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </>
                )}
            </div>

            {/* ── Mobile full-page overlay (at root level to escape stacking contexts) ── */}
            <AnimatePresence>
                {selected && (
                    <motion.div
                        key="mobile-overlay"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="lg:hidden fixed inset-0 z-[100] bg-[#050505] flex flex-col"
                    >
                        {/* Fixed top bar - always visible */}
                        <div className="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-white/10 bg-[#050505]">
                            <div className="flex items-center gap-3">
                                <Brain className="w-5 h-5 text-[#22c55e]" />
                                <div>
                                    <div className="text-sm font-black text-white uppercase tracking-tight">{selected.symbol}</div>
                                    <div className="text-[10px] text-white/40">{selected.name} • {selected.market || 'NSE'}</div>
                                </div>
                            </div>
                            <button
                                onClick={() => setSelected(null)}
                                className="p-2.5 rounded-xl bg-white/10 hover:bg-white/20 text-white/70 hover:text-white transition-all active:scale-90"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Scrollable content */}
                        <div className="flex-1 overflow-y-auto custom-scrollbar">
                            <DetailPanel
                                stock={selected}
                                mode={explainMode}
                                onExplainToggle={() => setExplainMode(m => m === 'simple' ? 'technical' : 'simple')}
                                onTrade={() => {
                                    setActiveSymbol(selected.symbol);
                                    if (onPageChange) onPageChange('demo');
                                }}
                            />
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            <style>{`
                .custom-scrollbar::-webkit-scrollbar { width: 4px; }
                .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
                .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 99px; }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(34,197,94,0.5); }
            `}</style>
        </div>
    );
}
