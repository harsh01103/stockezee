import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Database, TrendingUp, ShieldCheck, FileText } from 'lucide-react';

export const UniverseHealth: React.FC = () => {
    const [stats, setStats] = useState({
        total: 0,
        nse: 0,
        bse: 0,
        etfs: 0,
        doc_enabled: 0
    });

    useEffect(() => {
        // In a real env, this would be an API call to /api/universe/health
        // For now, we simulate pulling the summary stats
        setStats({
            total: 5412,
            nse: 2134,
            bse: 3278,
            etfs: 145,
            doc_enabled: 5267
        });
    }, []);

    return (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl mb-8">
            <div className="flex items-center gap-3 mb-6">
                <Database className="text-[#22c55e]" size={24} />
                <h2 className="text-xl font-bold text-white">Security Master Health</h2>
                <span className="ml-auto bg-[#22c55e]/10 text-[#22c55e] px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider">
                    Synced Today
                </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
                    <div className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">Total Equities</div>
                    <div className="text-2xl font-black text-white">{stats.total.toLocaleString()}</div>
                </div>
                
                <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
                    <div className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1 flex items-center gap-1.5">
                        <TrendingUp size={14} className="text-blue-400" />
                        NSE / BSE Split
                    </div>
                    <div className="text-xl font-bold text-white">
                        <span className="text-blue-400">{stats.nse}</span> <span className="text-slate-500 text-sm">/</span> <span className="text-purple-400">{stats.bse}</span>
                    </div>
                </div>

                <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
                    <div className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1 flex items-center gap-1.5">
                        <ShieldCheck size={14} className="text-orange-400" />
                        Active ETFs
                    </div>
                    <div className="text-2xl font-black text-white">{stats.etfs}</div>
                </div>

                <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
                    <div className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1 flex items-center gap-1.5">
                        <FileText size={14} className="text-teal-400" />
                        Doc Intelligence
                    </div>
                    <div className="text-2xl font-black text-white">
                        {stats.doc_enabled.toLocaleString()}
                        <span className="text-xs text-slate-500 font-normal ml-1">eligible</span>
                    </div>
                </div>
            </div>
        </div>
    );
};
