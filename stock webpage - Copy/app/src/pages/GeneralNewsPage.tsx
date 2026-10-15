import { useEffect, useState } from 'react';
import { Newspaper, Globe, ShieldCheck, ArrowUpRight, Activity } from 'lucide-react';
import { motion } from 'framer-motion';

interface NewsItem {
    title: string;
    link: string;
    pubDate: string;
    source: string;
    contentSnippet: string;
    isVerified: boolean;
}

export function GeneralNewsPage() {
    const [news, setNews] = useState<NewsItem[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch('/api/global-news')
            .then(res => res.json())
            .then(data => {
                setNews(data.news || []);
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, []);

    const containerVars = {
        hidden: { opacity: 0 },
        visible: { opacity: 1, transition: { staggerChildren: 0.1 } }
    };

    const itemVars = {
        hidden: { opacity: 0, y: 15 },
        visible: { opacity: 1, y: 0, transition: { duration: 0.4 } }
    };

    return (
        <div className="min-h-screen bg-[#050505] font-sans selection:bg-[#22c55e]/30">
            {/* Background Elements */}
            <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
                <div className="absolute top-0 right-1/4 w-[40vw] h-[40vw] bg-white/[0.015] blur-[150px] rounded-full mix-blend-screen" />
                <div className="absolute bottom-0 left-1/4 w-[30vw] h-[30vw] bg-[#22c55e]/5 blur-[120px] rounded-full mix-blend-screen" />
                <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.15] mix-blend-overlay pointer-events-none" />
            </div>

            <div className="relative z-10 max-w-[1400px] mx-auto px-6 py-8">

                {/* Header */}
                <div className="mb-12 border-b border-white/5 pb-10">
                    <motion.h1 initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="text-4xl md:text-5xl font-black text-white flex items-center tracking-tighter mb-4">
                        <Globe className="w-8 h-8 text-[#22c55e] mr-4 opacity-80" />
                        Global News
                    </motion.h1>
                    <motion.p initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="text-white/40 font-light text-sm tracking-widest uppercase">
                        Real-time updates from trusted financial news sources globally.
                    </motion.p>
                </div>

                {loading ? (
                    <div className="flex flex-col justify-center items-center py-32 space-y-6">
                        <div className="relative w-16 h-16">
                            <div className="absolute inset-0 border-2 border-t-[#22c55e] border-transparent rounded-full animate-spin" />
                            <Activity className="w-8 h-8 text-white/40 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 animate-pulse" />
                        </div>
                        <p className="text-white/60 font-black uppercase tracking-widest text-sm animate-pulse">Scraping global newswires...</p>
                    </div>
                ) : (
                    <motion.div variants={containerVars} initial="hidden" animate="visible" className="space-y-6">
                        {news.map((item, idx) => (
                            <motion.div
                                variants={itemVars}
                                key={idx}
                                className="bg-white/[0.01] p-8 rounded-3xl border border-white/5 hover:border-white/10 hover:bg-white/[0.02] transition-colors group relative overflow-hidden"
                            >
                                <div className="absolute top-0 right-0 w-32 h-32 bg-[#22c55e]/5 blur-[60px] rounded-full group-hover:bg-[#22c55e]/10 transition-colors pointer-events-none" />

                                <div className="relative z-10 flex flex-wrap items-center justify-between gap-4 mb-6">
                                    <span className="px-3 py-1.5 bg-[#22c55e]/10 text-emerald-300 text-[10px] rounded-full flex items-center font-bold tracking-widest uppercase border border-[#22c55e]/20">
                                        <ShieldCheck className="w-3.5 h-3.5 mr-1.5" />
                                        Verified Source
                                    </span>
                                    <span className="font-mono text-[11px] font-medium text-white/30 uppercase tracking-widest">
                                        {new Date(item.pubDate).toLocaleString([], { dateStyle: 'long', timeStyle: 'short' })}
                                    </span>
                                </div>

                                <h3 className="text-2xl font-black mb-4 leading-snug tracking-tight">
                                    <a href={item.link} target="_blank" rel="noopener noreferrer" className="hover:text-[#22c55e] text-white transition-colors flex items-start gap-3">
                                        <Newspaper className="w-6 h-6 mt-1 opacity-20 group-hover:opacity-40 shrink-0 transition-opacity" />
                                        <span>{item.title}</span>
                                    </a>
                                </h3>

                                <p className="text-white/40 font-light text-base mb-8 leading-relaxed">
                                    {item.contentSnippet || "Full analytical report available on destination site."}
                                </p>

                                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center text-xs font-bold text-white/30 pt-6 border-t border-white/5 gap-4">
                                    <span className="uppercase tracking-widest">Source: {item.source.split(' - ')[0]}</span>
                                    <a href={item.link} target="_blank" rel="noopener noreferrer" className="text-[#22c55e]/80 hover:text-[#22c55e] flex items-center gap-1.5 uppercase tracking-widest transition-colors pb-1 border-b border-transparent hover:border-[#22c55e]">
                                        Read Dispatch <ArrowUpRight className="w-3.5 h-3.5" />
                                    </a>
                                </div>
                            </motion.div>
                        ))}

                        {news.length === 0 && (
                            <div className="text-center py-20 text-white/30 border border-dashed border-white/10 rounded-3xl bg-white/[0.01]">
                                <Globe className="w-12 h-12 mx-auto mb-4 opacity-20" />
                                <p className="font-bold text-lg text-white/50 tracking-tight">No News Available</p>
                                <p className="text-sm font-light mt-2 max-w-sm mx-auto">We couldn't find any major market news at the moment. Please check back later.</p>
                            </div>
                        )}
                    </motion.div>
                )}
            </div>
        </div>
    );
}
