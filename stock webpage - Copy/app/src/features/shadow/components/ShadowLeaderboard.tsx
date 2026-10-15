import { Trophy, User, Cpu } from 'lucide-react';
import { motion } from 'framer-motion';

export function ShadowLeaderboard() {
    const leaderboard = [
        {
            rank: 1,
            name: 'Alpha Engine v5.0',
            type: 'MODEL',
            winRate: 62.5,
            pnl: 45200,
            sharpe: 2.1
        },
        {
            rank: 2,
            name: 'Human Benchmark',
            type: 'HUMAN',
            winRate: 48.2,
            pnl: 12500,
            sharpe: 1.2
        }
    ];

    return (
        <div className="bg-[#0a0a0a] rounded-3xl border border-white/10 shadow-2xl p-6 lg:p-8 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-64 h-64 bg-[#22c55e]/10 blur-[100px] rounded-full pointer-events-none" />

            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 mb-8 relative z-10">
                <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-[#22c55e]/10 border border-[#22c55e]/20 flex items-center justify-center">
                        <Trophy className="w-6 h-6 text-[#22c55e]" />
                    </div>
                    <div>
                        <h2 className="text-2xl font-black text-white tracking-tight uppercase">Shadow Mode</h2>
                        <p className="text-xs text-white/40 font-bold tracking-widest uppercase mt-1">Human vs Machine Performance</p>
                    </div>
                </div>
            </div>

            <div className="space-y-4 relative z-10">
                {leaderboard.map((entry, idx) => (
                    <motion.div 
                        key={entry.name}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.1 }}
                        className={`p-5 rounded-2xl border ${entry.type === 'MODEL' ? 'bg-[#22c55e]/[0.02] border-[#22c55e]/20' : 'bg-white/[0.02] border-white/5'} flex flex-col md:flex-row md:items-center justify-between gap-4`}
                    >
                        <div className="flex items-center gap-4">
                            <div className="text-2xl font-black text-white/20">#{entry.rank}</div>
                            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${entry.type === 'MODEL' ? 'bg-[#22c55e]/20 text-[#22c55e]' : 'bg-white/10 text-white/60'}`}>
                                {entry.type === 'MODEL' ? <Cpu className="w-5 h-5" /> : <User className="w-5 h-5" />}
                            </div>
                            <div>
                                <h3 className={`text-lg font-bold ${entry.type === 'MODEL' ? 'text-white' : 'text-white/80'}`}>{entry.name}</h3>
                                <div className="text-xs text-white/40 font-mono tracking-widest">{entry.type}</div>
                            </div>
                        </div>

                        <div className="flex items-center gap-8">
                            <div className="text-center">
                                <div className="text-[10px] text-white/40 uppercase tracking-widest font-bold mb-1">Win Rate</div>
                                <div className="text-xl font-black text-white">{entry.winRate}%</div>
                            </div>
                            <div className="text-center">
                                <div className="text-[10px] text-white/40 uppercase tracking-widest font-bold mb-1">Sharpe</div>
                                <div className="text-xl font-black text-white">{entry.sharpe}</div>
                            </div>
                            <div className="text-center">
                                <div className="text-[10px] text-white/40 uppercase tracking-widest font-bold mb-1">Total PnL</div>
                                <div className={`text-xl font-black ${entry.pnl >= 0 ? 'text-[#22c55e]' : 'text-red-500'}`}>
                                    ${entry.pnl.toLocaleString()}
                                </div>
                            </div>
                        </div>
                    </motion.div>
                ))}
            </div>
        </div>
    );
}
