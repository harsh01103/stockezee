import { useAuth } from '../context/AuthProvider';
import { Activity, Shield, Server, Lock, Clock } from 'lucide-react';
import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabaseClient';
import type { Page } from '@/App';
import { motion } from 'framer-motion';
import { RegimeWidget } from '@/features/regime/components/RegimeWidget';
import { ShadowLeaderboard } from '@/features/shadow/components/ShadowLeaderboard';
import { UniverseHealth } from '@/features/quality/components/UniverseHealth';

export function DashboardPage({ onPageChange }: { onPageChange: (page: Page) => void }) {
    const { user, loading } = useAuth();
    const [username, setUsername] = useState<string | null>(null);

    useEffect(() => {
        if (user) {
            if (user.user_metadata?.username) {
                setUsername(user.user_metadata.username);
            } else {
                const fetchUsername = async () => {
                    const { data } = await supabase.from('profiles').select('username').eq('email', user.email).maybeSingle();
                    if (data?.username) {
                        setUsername(data.username);
                    } else {
                        setUsername(user.email?.split('@')[0] || 'User');
                    }
                };
                fetchUsername();
            }
        }
    }, [user]);

    if (loading) {
        return (
            <div className="min-h-screen bg-[#050505] flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                    <Server className="w-8 h-8 text-[#22c55e] animate-pulse" />
                    <div className="text-white/40 text-xs font-black uppercase tracking-widest animate-pulse">Establishing Secure Uplink...</div>
                </div>
            </div>
        );
    }

    if (!user) {
        return (
            <div className="min-h-screen bg-[#050505] flex flex-col items-center justify-center p-4 relative overflow-hidden">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[40vw] h-[40vw] bg-red-500/5 blur-[120px] rounded-full pointer-events-none" />
                <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="flex flex-col items-center text-center relative z-10 p-12 bg-white/[0.01] border border-white/5 rounded-3xl">
                    <Lock className="w-16 h-16 text-red-500/50 mb-6" />
                    <h2 className="text-3xl font-black text-white mb-2 tracking-tight">Access Restricted</h2>
                    <p className="text-white/40 mb-8 font-light max-w-sm">Deeper platform infrastructure requires authorized terminal access.</p>
                    <button
                        onClick={() => onPageChange('login')}
                        className="bg-white text-black px-10 py-4 rounded-xl font-black uppercase tracking-widest text-sm hover:bg-gray-200 transition-colors shadow-[0_0_20px_rgba(255,255,255,0.1)]"
                    >
                        Initialize Login
                    </button>
                </motion.div>
            </div>
        );
    }

    const containerVars = {
        hidden: { opacity: 0 },
        visible: { opacity: 1, transition: { staggerChildren: 0.1 } }
    };

    const itemVars = {
        hidden: { opacity: 0, y: 20 },
        visible: { opacity: 1, y: 0, transition: { duration: 0.5 } }
    };

    return (
        <div className="min-h-screen bg-[#050505] font-sans selection:bg-[#22c55e]/30">
            {/* Background Elements */}
            <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
                <div className="absolute top-0 right-1/4 w-[40vw] h-[40vw] bg-white/[0.015] blur-[150px] rounded-full mix-blend-screen" />
                <div className="absolute bottom-0 left-1/4 w-[30vw] h-[30vw] bg-[#22c55e]/5 blur-[120px] rounded-full mix-blend-screen" />
                <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.1] mix-blend-overlay pointer-events-none" />
            </div>

            <div className="relative z-10 max-w-[1200px] mx-auto px-6 py-16">

                <motion.div initial="hidden" animate="visible" variants={containerVars} className="mb-12 border-b border-white/5 pb-10 flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
                    <div>

                        <motion.h1 variants={itemVars} className="text-4xl md:text-5xl font-black text-white flex items-center tracking-tighter mb-2">
                            Infrastructure Command
                        </motion.h1>
                        <motion.p variants={itemVars} className="text-white/40 font-light text-lg flex items-center gap-2">
                            Welcome back, <span className="text-white font-bold">{username || 'User'}</span>
                        </motion.p>
                    </div>
                </motion.div>

                <motion.div variants={containerVars} initial="hidden" animate="visible">
                    <motion.div variants={itemVars}>
                        <UniverseHealth />
                    </motion.div>
                </motion.div>

                <motion.div variants={containerVars} initial="hidden" animate="visible" className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">

                    <motion.div variants={itemVars} className="bg-white/[0.01] border border-white/5 rounded-3xl p-8 hover:bg-white/[0.02] transition-colors relative overflow-hidden group">
                        <div className="absolute top-0 right-0 w-32 h-32 bg-[#22c55e]/5 blur-[50px] rounded-full pointer-events-none group-hover:bg-[#22c55e]/10 transition-colors" />
                        <Shield className="w-8 h-8 text-[#22c55e]/60 mb-6" />
                        <h3 className="text-sm font-black text-white/40 uppercase tracking-widest mb-2">Security Clearance</h3>
                        <p className="text-xl font-bold text-white flex items-center gap-3">
                            <span className="w-2.5 h-2.5 rounded-full bg-[#22c55e] shadow-[0_0_10px_rgba(34,197,94,0.5)]"></span>
                            Verified Terminal
                        </p>
                    </motion.div>

                    <motion.div variants={itemVars} className="bg-white/[0.01] border border-white/5 rounded-3xl p-8 hover:bg-white/[0.02] transition-colors relative overflow-hidden group">
                        <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 blur-[50px] rounded-full pointer-events-none group-hover:bg-white/10 transition-colors" />
                        <Clock className="w-8 h-8 text-white/30 mb-6" />
                        <h3 className="text-sm font-black text-white/40 uppercase tracking-widest mb-2">Last Uplink</h3>
                        <p className="text-lg font-bold text-white/90">
                            {user.last_sign_in_at ? new Date(user.last_sign_in_at).toLocaleString() : 'Just now'}
                        </p>
                    </motion.div>

                    <motion.div variants={itemVars} className="bg-white/[0.01] border border-white/5 rounded-3xl p-8 hover:bg-white/[0.02] transition-colors relative overflow-hidden group">
                        <div className="absolute top-0 right-0 w-32 h-32 bg-sky-500/5 blur-[50px] rounded-full pointer-events-none group-hover:bg-sky-500/10 transition-colors" />
                        <Activity className="w-8 h-8 text-sky-400/50 mb-6" />
                        <h3 className="text-sm font-black text-white/40 uppercase tracking-widest mb-2">Account Status</h3>
                        <p className="text-lg font-bold text-sky-400">
                            Active / Quant Member
                        </p>
                    </motion.div>

                    <motion.div variants={itemVars}>
                        <RegimeWidget />
                    </motion.div>

                </motion.div>

                <motion.div variants={containerVars} initial="hidden" animate="visible" className="mt-8">
                    <motion.div variants={itemVars}>
                        <ShadowLeaderboard />
                    </motion.div>
                </motion.div>

            </div>
        </div>
    );
}
