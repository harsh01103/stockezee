import { CalendarDays, AlertTriangle, TrendingUp, Briefcase, Activity } from 'lucide-react';
import { motion } from 'framer-motion';

const events = [
    {
        date: 'March 1, 2026',
        title: 'GST Council Meeting',
        impact: 'High',
        description: 'Expected revisions on tax slabs for critical FMCG and cement sectors. Anticipate high volatility in these indexes.',
        type: 'domestic'
    },
    {
        date: 'March 15, 2026',
        title: 'RBI Monetary Policy Update',
        impact: 'Critical',
        description: 'Governor announcement regarding the repo rate. A highly anticipated 25bps cut could trigger a massive bank-nifty rally.',
        type: 'domestic'
    },
    {
        date: 'April 10, 2026',
        title: 'Q4 Earnings Season Kickoff',
        impact: 'High',
        description: 'TCS and Infosys to report earnings, setting the tone for the IT sector for the upcoming financial year.',
        type: 'earnings'
    },
    {
        date: 'May 1, 2026',
        title: 'Maharashtra State Elections Result',
        impact: 'Critical',
        description: 'State election outcomes often trigger macroscopic sentiment shifts in infrastructure and domestic institutional flows.',
        type: 'political'
    },
    {
        date: 'June 5, 2026',
        title: 'US Fed Interest Rate Decision',
        impact: 'Critical',
        description: 'Global macro impact. A dovish stance will increase FII (Foreign Institutional Investor) flows into Indian equities.',
        type: 'global'
    }
];

export function EconomicCalendarPage() {
    return (
        <div className="min-h-screen bg-[#050505] font-sans selection:bg-[#22c55e]/30">
            {/* Background Elements */}
            <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
                <div className="absolute top-0 left-1/4 w-[40vw] h-[40vw] bg-white/[0.015] blur-[150px] rounded-full mix-blend-screen" />
                <div className="absolute bottom-0 right-1/4 w-[30vw] h-[30vw] bg-[#22c55e]/5 blur-[120px] rounded-full mix-blend-screen" />
                <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.15] mix-blend-overlay pointer-events-none" />
            </div>

            <div className="relative z-10 max-w-[1200px] mx-auto px-6 py-16">

                {/* Header */}
                <div className="mb-12 border-b border-white/5 pb-10">

                    <motion.h1 initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="text-4xl md:text-5xl font-black text-white flex items-center tracking-tighter mb-4">
                        <CalendarDays className="w-8 h-8 text-[#22c55e] mr-4 opacity-80" />
                        Economic Calendar
                    </motion.h1>
                    <motion.p initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="text-white/40 font-light text-lg max-w-2xl">
                        Critical upcoming domestic and global catalysts algorithmically tracking parameters that drive structural market volatility.
                    </motion.p>
                </div>

                {/* Timeline layout */}
                <div className="space-y-6">
                    {events.map((evt, idx) => (
                        <motion.div
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: idx * 0.1, duration: 0.5 }}
                            key={idx}
                            className="bg-white/[0.01] border border-white/5 hover:border-white/10 hover:bg-white/[0.02] rounded-3xl p-6 sm:p-8 flex flex-col md:flex-row gap-6 items-start md:items-center transition-all group relative overflow-hidden"
                        >
                            <div className="absolute top-0 right-0 w-32 h-32 bg-[#22c55e]/5 blur-[50px] rounded-full pointer-events-none group-hover:bg-[#22c55e]/10 transition-colors" />

                            <div className="w-48 shrink-0 border-l-2 border-[#22c55e]/30 pl-4 py-2 relative z-10">
                                <div className="text-xs text-[#22c55e]/60 font-black uppercase tracking-widest mb-1">Date</div>
                                <div className="text-xl font-bold text-white tracking-tight">{evt.date}</div>
                            </div>

                            <div className="flex-1 relative z-10">
                                <div className="flex items-center gap-3 mb-2">
                                    {evt.type === 'political' && <AlertTriangle className="w-4 h-4 text-orange-400" />}
                                    {evt.type === 'earnings' && <Briefcase className="w-4 h-4 text-purple-400" />}
                                    {evt.type === 'global' && <TrendingUp className="w-4 h-4 text-sky-400" />}
                                    {evt.type === 'domestic' && <Activity className="w-4 h-4 text-[#22c55e]" />}
                                    <h3 className="text-2xl font-black text-white/90 tracking-tight">{evt.title}</h3>
                                </div>
                                <p className="text-white/40 font-light leading-relaxed max-w-2xl">{evt.description}</p>
                            </div>

                            <div className="shrink-0 relative z-10">
                                <span className={`px-4 py-2 text-xs uppercase font-black tracking-widest rounded-xl flex items-center gap-2 border ${evt.impact === 'Critical'
                                    ? 'bg-red-500/10 text-red-500 border-red-500/20 shadow-[0_0_15px_rgba(239,68,68,0.15)]'
                                    : 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                                    }`}>
                                    <div className={`w-1.5 h-1.5 rounded-full animate-pulse ${evt.impact === 'Critical' ? 'bg-red-500' : 'bg-amber-500'}`} />
                                    {evt.impact}
                                </span>
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </div>
    );
}
