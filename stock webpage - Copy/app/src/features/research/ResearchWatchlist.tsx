import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, FileText, AlertTriangle } from 'lucide-react';
// import { createChart } from 'lightweight-charts'; // Ensure installed if rendering real charts

interface TradePlan {
    id: string;
    symbol: string;
    date: string;
    setup_type: string;
    opportunity_score: number;
    trade_readiness: 'READY' | 'DEVELOPING' | 'EXTENDED';
    entry_trigger: number;
    stop_loss: number;
    target_1: number;
    risk_reward: number;
    expected_horizon: string;
    thesis: {
        summary: string;
        bulletPoints: string[];
    };
    chart_annotations: any[];
}

export function ResearchWatchlist() {
    const [watchlist, setWatchlist] = useState<TradePlan[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function fetchWatchlist() {
            try {
                // Fetch next_session (READY) and next_week (DEVELOPING)
                const res = await axios.get('http://localhost:4000/api/research/watchlist?horizon=all');
                if (res.data.success) {
                    setWatchlist(res.data.watchlist || []);
                }
            } catch (err) {
                console.error('Failed to fetch research watchlist:', err);
            } finally {
                setLoading(false);
            }
        }
        fetchWatchlist();
    }, []);

    if (loading) {
        return <div className="p-8 text-center text-gray-500">Loading Deep Research Intelligence...</div>;
    }

    if (watchlist.length === 0) {
        return <div className="p-8 text-center text-gray-500">No actionable setups found by the research engine today.</div>;
    }

    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold tracking-tight text-white flex items-center">
                <TrendingUp className="mr-2 text-indigo-400" /> Quantitative Research Watchlist
            </h2>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                {watchlist.map((plan) => (
                    <Card key={plan.id} className="bg-slate-900 border-slate-800 text-white shadow-lg overflow-hidden">
                        <CardHeader className="border-b border-slate-800 bg-slate-950 pb-4">
                            <div className="flex justify-between items-start">
                                <div>
                                    <CardTitle className="text-xl font-bold">{plan.symbol}</CardTitle>
                                    <p className="text-xs text-slate-400 mt-1">{plan.setup_type} • Horizon: {plan.expected_horizon}</p>
                                </div>
                                <div className="flex flex-col items-end gap-2">
                                    <Badge 
                                        variant="outline" 
                                        className={plan.trade_readiness === 'READY' ? 'text-emerald-400 border-emerald-400/30' : 'text-amber-400 border-amber-400/30'}
                                    >
                                        {plan.trade_readiness}
                                    </Badge>
                                    <span className="text-sm font-semibold text-slate-300">
                                        Score: {plan.opportunity_score}/100
                                    </span>
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent className="pt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-4">
                                <div>
                                    <h4 className="text-sm font-semibold text-slate-400 flex items-center">
                                        <FileText className="w-4 h-4 mr-1" /> Explainability Thesis
                                    </h4>
                                    <ul className="mt-2 space-y-2 text-sm text-slate-300">
                                        {plan.thesis?.bulletPoints?.map((pt, i) => (
                                            <li key={i} className="flex items-start">
                                                <span className="text-indigo-400 mr-2">•</span>
                                                <span>{pt}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-sm bg-slate-800/50 p-3 rounded-md border border-slate-700">
                                    <div>
                                        <p className="text-slate-400 text-xs">Entry Trigger</p>
                                        <p className="font-mono text-emerald-400">₹{plan.entry_trigger}</p>
                                    </div>
                                    <div>
                                        <p className="text-slate-400 text-xs">Stop Loss</p>
                                        <p className="font-mono text-rose-400">₹{plan.stop_loss}</p>
                                    </div>
                                    <div>
                                        <p className="text-slate-400 text-xs">Primary Target</p>
                                        <p className="font-mono text-emerald-400">₹{plan.target_1}</p>
                                    </div>
                                    <div>
                                        <p className="text-slate-400 text-xs">Risk/Reward</p>
                                        <p className="font-mono text-white">{plan.risk_reward}x</p>
                                    </div>
                                </div>
                            </div>
                            
                            <div className="bg-slate-950 rounded border border-slate-800 flex items-center justify-center p-4">
                                {plan.chart_annotations && plan.chart_annotations.length > 0 ? (
                                    <div className="text-center">
                                        {/* Lightweight Charts instance would mount here */}
                                        <TrendingUp className="w-8 h-8 text-indigo-500 mx-auto mb-2 opacity-50" />
                                        <p className="text-xs text-slate-500">Annotated Chart Rendered (VCP Pivot: ₹{plan.entry_trigger})</p>
                                    </div>
                                ) : (
                                    <div className="text-center opacity-50">
                                        <AlertTriangle className="w-8 h-8 text-amber-500 mx-auto mb-2" />
                                        <p className="text-xs text-slate-400">No chart data available</p>
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
}
