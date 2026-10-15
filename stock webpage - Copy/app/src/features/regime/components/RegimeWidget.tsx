import { Activity, TrendingUp, ShieldAlert } from 'lucide-react';
import { motion } from 'framer-motion';

export function RegimeWidget() {
    // In a real app, this would fetch from /api/regime
    const regimeData = {
        regime: 'BULL_TRENDING',
        confidence: 88,
        activeStrategies: ['VCP_BREAKOUT', 'MOMENTUM_LONG'],
        disabledStrategies: ['MEAN_REVERSION_LONG']
    };

    const getIcon = () => {
        if (regimeData.regime.includes('BULL')) return <TrendingUp className="w-8 h-8 text-[#22c55e]/60 mb-6" />;
        if (regimeData.regime.includes('PANIC')) return <ShieldAlert className="w-8 h-8 text-red-500/60 mb-6" />;
        return <Activity className="w-8 h-8 text-amber-500/60 mb-6" />;
    };

    const getColor = () => {
        if (regimeData.regime.includes('BULL')) return 'text-[#22c55e]';
        if (regimeData.regime.includes('PANIC')) return 'text-red-500';
        return 'text-amber-500';
    };

    const getBgColor = () => {
        if (regimeData.regime.includes('BULL')) return 'bg-[#22c55e]/5 group-hover:bg-[#22c55e]/10';
        if (regimeData.regime.includes('PANIC')) return 'bg-red-500/5 group-hover:bg-red-500/10';
        return 'bg-amber-500/5 group-hover:bg-amber-500/10';
    };

    return (
        <motion.div className="bg-white/[0.01] border border-white/5 rounded-3xl p-8 hover:bg-white/[0.02] transition-colors relative overflow-hidden group">
            <div className={`absolute top-0 right-0 w-32 h-32 blur-[50px] rounded-full pointer-events-none transition-colors ${getBgColor()}`} />
            {getIcon()}
            <h3 className="text-sm font-black text-white/40 uppercase tracking-widest mb-2">Market Regime</h3>
            <p className={`text-xl font-bold flex items-center gap-3 ${getColor()}`}>
                <span className={`w-2.5 h-2.5 rounded-full ${regimeData.regime.includes('BULL') ? 'bg-[#22c55e] shadow-[0_0_10px_rgba(34,197,94,0.5)]' : 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]'}`}></span>
                {regimeData.regime.replace('_', ' ')}
            </p>
            <div className="mt-4 pt-4 border-t border-white/5">
                <div className="text-[10px] text-white/30 uppercase tracking-widest font-bold mb-2">Active Strategies</div>
                <div className="flex flex-wrap gap-2">
                    {regimeData.activeStrategies.map(s => (
                        <span key={s} className="px-2 py-1 rounded bg-white/5 text-[9px] text-white/60 font-mono">
                            {s}
                        </span>
                    ))}
                </div>
            </div>
        </motion.div>
    );
}
