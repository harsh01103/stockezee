import React, { useState, useEffect, useCallback } from 'react';
import { getTrades, getDailyPnL, clearTrades, type TradeEntry } from '../store/tradeLog';
import { useAuth } from '../context/AuthProvider';
import { CalendarDays, TrendingUp, TrendingDown, Trash2, ChevronLeft, ChevronRight, BarChart2, RefreshCw, Loader2 } from 'lucide-react';

const TradeHistory: React.FC = () => {
    const { session } = useAuth();
    const [trades, setTrades] = useState<TradeEntry[]>([]);
    const [dailyPnL, setDailyPnL] = useState<Record<string, { pnl: number; trades: number }>>({});
    const [view, setView] = useState<'list' | 'calendar'>('list');
    const [loading, setLoading] = useState(false);
    const [calMonth, setCalMonth] = useState(() => {
        const now = new Date();
        return { year: now.getFullYear(), month: now.getMonth() };
    });

    const refresh = useCallback(async () => {
        if (!session) return;
        setLoading(true);
        try {
            const [t, d] = await Promise.all([getTrades(), getDailyPnL()]);
            setTrades(t);
            setDailyPnL(d);
        } catch (e) {
            console.error('Failed to fetch trades:', e);
        }
        setLoading(false);
    }, [session]);

    useEffect(() => {
        refresh();
    }, [refresh]);

    if (!session) return null; // Don't render if not logged in

    const totalPnL = trades.reduce((sum, t) => sum + (Number(t.pnl) || 0), 0);
    const totalTrades = trades.length;
    const wins = trades.filter(t => t.pnl != null && Number(t.pnl) > 0).length;
    const losses = trades.filter(t => t.pnl != null && Number(t.pnl) < 0).length;

    // Calendar helpers
    const daysInMonth = new Date(calMonth.year, calMonth.month + 1, 0).getDate();
    const firstDayOfWeek = new Date(calMonth.year, calMonth.month, 1).getDay();
    const monthName = new Date(calMonth.year, calMonth.month).toLocaleString('en-US', { month: 'long', year: 'numeric' });

    const prevMonth = () => {
        setCalMonth(prev => {
            const d = new Date(prev.year, prev.month - 1);
            return { year: d.getFullYear(), month: d.getMonth() };
        });
    };
    const nextMonth = () => {
        const now = new Date();
        const next = new Date(calMonth.year, calMonth.month + 1);
        if (next <= new Date(now.getFullYear(), now.getMonth() + 1)) {
            setCalMonth({ year: next.getFullYear(), month: next.getMonth() });
        }
    };

    const handleClear = async () => {
        if (window.confirm('Clear all trade history? This cannot be undone.')) {
            await clearTrades();
            refresh();
        }
    };

    return (
        <div className="bg-[#0f1629]/80 backdrop-blur-md rounded-2xl border border-white/10 p-3 sm:p-4 mt-6">
            {/* Header */}
            <div className="flex flex-wrap items-center justify-between mb-4 gap-2">
                <div className="flex items-center gap-2">
                    <CalendarDays className="w-5 h-5 text-emerald-400" />
                    <h3 className="text-base sm:text-lg font-semibold text-white">Trade Journal</h3>
                    <span className="text-xs text-white/40 ml-1">(last 30 days)</span>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setView('list')}
                        className={`px-3 py-1 rounded-lg text-xs font-medium transition ${view === 'list' ? 'bg-emerald-500/30 text-emerald-300' : 'text-white/50 hover:text-white/80'}`}
                    >
                        <BarChart2 className="w-3 h-3 inline mr-1" />Trades
                    </button>
                    <button
                        onClick={() => setView('calendar')}
                        className={`px-3 py-1 rounded-lg text-xs font-medium transition ${view === 'calendar' ? 'bg-emerald-500/30 text-emerald-300' : 'text-white/50 hover:text-white/80'}`}
                    >
                        P&L Calendar
                    </button>
                    <button onClick={refresh} className="p-1 text-white/30 hover:text-emerald-400 transition" title="Refresh">
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                    </button>
                    {trades.length > 0 && (
                        <button onClick={handleClear} className="p-1 text-white/30 hover:text-red-400 transition" title="Clear history">
                            <Trash2 className="w-4 h-4" />
                        </button>
                    )}
                </div>
            </div>

            {/* Summary Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3 mb-4">
                <div className="bg-white/5 rounded-xl p-3 text-center">
                    <div className="text-xs text-white/50">Total Trades</div>
                    <div className="text-lg font-bold text-white">{totalTrades}</div>
                </div>
                <div className="bg-white/5 rounded-xl p-3 text-center">
                    <div className="text-xs text-white/50">Net P&L</div>
                    <div className={`text-lg font-bold ${totalPnL >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {totalPnL >= 0 ? '+' : ''}₹{totalPnL.toFixed(2)}
                    </div>
                </div>
                <div className="bg-white/5 rounded-xl p-3 text-center">
                    <div className="text-xs text-white/50">Wins</div>
                    <div className="text-lg font-bold text-emerald-400">{wins}</div>
                </div>
                <div className="bg-white/5 rounded-xl p-3 text-center">
                    <div className="text-xs text-white/50">Losses</div>
                    <div className="text-lg font-bold text-red-400">{losses}</div>
                </div>
            </div>

            {/* List View */}
            {view === 'list' && (
                <div className="max-h-80 overflow-y-auto custom-scrollbar">
                    {loading && trades.length === 0 ? (
                        <div className="text-center text-white/30 py-8 text-sm flex items-center justify-center gap-2">
                            <Loader2 className="w-4 h-4 animate-spin" /> Loading trades...
                        </div>
                    ) : trades.length === 0 ? (
                        <div className="text-center text-white/30 py-8 text-sm">No trades in the last 30 days. Start trading to see your history here.</div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-xs min-w-[500px]">
                                <thead className="text-white/40 border-b border-white/10 sticky top-0 bg-[#0f1629]">
                                    <tr>
                                        <th className="py-2 text-left pl-2">Date & Time</th>
                                        <th className="py-2 text-left">Symbol</th>
                                        <th className="py-2 text-center">Side</th>
                                        <th className="py-2 text-right">Qty</th>
                                        <th className="py-2 text-right">Price</th>
                                        <th className="py-2 text-right">Total</th>
                                        <th className="py-2 text-right pr-2">P&L</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {trades.map(t => (
                                        <tr key={t.id} className="border-b border-white/5 hover:bg-white/5 transition">
                                            <td className="py-2.5 pl-2 text-white/50">
                                                {new Date(t.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' })}{' '}
                                                <span className="text-white/30">{new Date(t.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</span>
                                            </td>
                                            <td className="py-2.5 text-white/80 font-medium">
                                                {t.symbol}
                                                <span className={`ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full ${t.category === 'commodity' ? 'bg-amber-500/20 text-amber-300' : 'bg-[#22c55e]/20 text-[#22c55e]'}`}>
                                                    {t.category === 'commodity' ? 'MCX' : 'EQ'}
                                                </span>
                                            </td>
                                            <td className="py-2.5 text-center">
                                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${t.type === 'BUY' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-red-500/20 text-red-300'}`}>
                                                    {t.type}
                                                </span>
                                            </td>
                                            <td className="py-2.5 text-right text-white/70">{t.qty}</td>
                                            <td className="py-2.5 text-right text-white/70">₹{Number(t.price).toFixed(2)}</td>
                                            <td className="py-2.5 text-right text-white/60">₹{Number(t.total).toFixed(2)}</td>
                                            <td className="py-2.5 text-right pr-2">
                                                {t.pnl != null ? (
                                                    <span className={`flex items-center justify-end gap-0.5 font-medium ${Number(t.pnl) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                                        {Number(t.pnl) >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                                        {Number(t.pnl) >= 0 ? '+' : ''}₹{Number(t.pnl).toFixed(2)}
                                                    </span>
                                                ) : (
                                                    <span className="text-white/20">—</span>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}

            {/* Calendar View */}
            {view === 'calendar' && (
                <div>
                    <div className="flex items-center justify-between mb-3">
                        <button onClick={prevMonth} className="p-1 text-white/50 hover:text-white transition"><ChevronLeft className="w-4 h-4" /></button>
                        <span className="text-sm font-medium text-white/80">{monthName}</span>
                        <button onClick={nextMonth} className="p-1 text-white/50 hover:text-white transition"><ChevronRight className="w-4 h-4" /></button>
                    </div>
                    <div className="grid grid-cols-7 gap-1 text-center">
                        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => (
                            <div key={d} className="text-[10px] text-white/40 font-medium py-1">{d}</div>
                        ))}
                        {Array.from({ length: firstDayOfWeek }).map((_, i) => (
                            <div key={`empty-${i}`} className="h-10" />
                        ))}
                        {Array.from({ length: daysInMonth }).map((_, i) => {
                            const day = i + 1;
                            const dateKey = `${calMonth.year}-${String(calMonth.month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                            const data = dailyPnL[dateKey];
                            const isToday = (() => {
                                const now = new Date();
                                return day === now.getDate() && calMonth.month === now.getMonth() && calMonth.year === now.getFullYear();
                            })();

                            return (
                                <div
                                    key={day}
                                    className={`h-10 rounded-lg flex flex-col items-center justify-center text-[11px] relative transition
                                        ${isToday ? 'ring-1 ring-emerald-400/50' : ''}
                                        ${data ? (data.pnl > 0 ? 'bg-emerald-500/15' : data.pnl < 0 ? 'bg-red-500/15' : 'bg-white/5') : 'bg-transparent'}
                                    `}
                                    title={data ? `${data.trades} trade(s), P&L: ₹${data.pnl.toFixed(2)}` : ''}
                                >
                                    <span className={`${isToday ? 'text-emerald-300 font-bold' : 'text-white/60'}`}>{day}</span>
                                    {data && (
                                        <span className={`text-[8px] font-semibold ${data.pnl > 0 ? 'text-emerald-400' : data.pnl < 0 ? 'text-red-400' : 'text-white/40'}`}>
                                            {data.pnl > 0 ? '+' : ''}{data.pnl !== 0 ? `₹${Math.abs(data.pnl).toFixed(0)}` : `${data.trades}t`}
                                        </span>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};

export default TradeHistory;
