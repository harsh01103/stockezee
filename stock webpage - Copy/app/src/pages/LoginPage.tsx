import { useState } from 'react';
import { supabase } from '../lib/supabaseClient';
import { TrendingUp, Mail, Lock, User, ArrowRight, Loader2, Eye, EyeOff } from 'lucide-react';
import React from 'react';
import type { Page } from '@/App';
import { motion } from 'framer-motion';

export function LoginPage({ isSignup = false, onPageChange }: { isSignup?: boolean, onPageChange: (page: Page) => void }) {
    const [loginIdentifier, setLoginIdentifier] = useState('');
    const [username, setUsername] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<{ text: React.ReactNode; type: 'success' | 'error' } | null>(null);

    const handleAuth = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setMessage(null);

        if (isSignup) {
            if (password !== confirmPassword) {
                setMessage({ text: "Passwords do not match.", type: 'error' });
                setLoading(false);
                return;
            }

            const { data: existingUser } = await supabase.from('profiles').select('username').eq('username', username).maybeSingle();

            if (existingUser) {
                setMessage({ text: "This username is already taken. Please choose a different one.", type: 'error' });
                setLoading(false);
                return;
            }

            const { error, data } = await supabase.auth.signUp({
                email, password,
                options: { data: { username } }
            });

            if (error) {
                if (error.message.includes("already registered")) {
                    setMessage({ text: 'Email already registered. Please log in instead.', type: 'error' });
                } else if (error.message.includes("Password should contain")) {
                    setMessage({
                        text: (
                            <div className="space-y-1 text-left font-sans text-xs">
                                <p className="font-bold uppercase tracking-widest text-red-500 mb-2">Protocol Requirement:</p>
                                <ul className="list-disc pl-5 opacity-80 space-y-1">
                                    <li>One lowercase letter (a-z)</li>
                                    <li>One uppercase letter (A-Z)</li>
                                    <li>One number (0-9)</li>
                                    <li>One special character (!@#$%^&*)</li>
                                </ul>
                            </div>
                        ),
                        type: 'error'
                    });
                } else {
                    setMessage({ text: error.message, type: 'error' });
                }
                setLoading(false);
                return;
            } else if (data?.user?.identities?.length === 0) {
                setMessage({ text: 'Email already registered. Please log in instead.', type: 'error' });
                setLoading(false);
                return;
            }

            await supabase.from('profiles').insert([{ username, email }]);

            setMessage({ text: 'Account initialized successfully! Redirecting...', type: 'success' });
            setTimeout(() => onPageChange('dashboard'), 1500);

        } else {
            let targetEmail = loginIdentifier;

            if (!loginIdentifier.includes('@')) {
                const { data: profileData, error: profileError } = await supabase.from('profiles').select('email').eq('username', loginIdentifier).maybeSingle();

                if (profileError || !profileData) {
                    setMessage({ text: "Username not found. Please try again or create an account.", type: 'error' });
                    setLoading(false);
                    return;
                }
                targetEmail = profileData.email;
            }

            const { error } = await supabase.auth.signInWithPassword({
                email: targetEmail,
                password,
            });

            if (error) {
                if (error.message.includes('Invalid login credentials')) {
                    setMessage({ text: "Invalid credentials. If you're new here, initialize an account first.", type: 'error' });
                } else {
                    setMessage({ text: error.message, type: 'error' });
                }
            } else {
                setMessage({ text: 'Connection established! Redirecting...', type: 'success' });
                setTimeout(() => onPageChange('dashboard'), 1000);
            }
        }
        setLoading(false);
    };

    const containerVars = {
        hidden: { opacity: 0 },
        visible: { opacity: 1, transition: { staggerChildren: 0.1 } }
    };

    const itemVars = {
        hidden: { opacity: 0, scale: 0.95 },
        visible: { opacity: 1, scale: 1, transition: { duration: 0.5 } }
    };

    return (
        <div className="min-h-screen bg-[#050505] font-sans selection:bg-[#22c55e]/30 flex items-center justify-center p-4 overflow-hidden relative">

            {/* Background Elements */}
            <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
                <div className="absolute top-1/4 left-1/4 w-[50vw] h-[50vw] bg-white/[0.015] blur-[150px] rounded-full mix-blend-screen" />
                <div className="absolute bottom-1/4 right-1/4 w-[30vw] h-[30vw] bg-[#22c55e]/5 blur-[120px] rounded-full mix-blend-screen" />
                <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.1] mix-blend-overlay pointer-events-none" />
            </div>

            <motion.div initial="hidden" animate="visible" variants={containerVars} className="w-full max-w-md bg-[#0a0a0a]/80 backdrop-blur-xl border border-white/5 rounded-3xl p-8 sm:p-10 shadow-2xl relative z-10">
                <div className="absolute top-0 right-0 w-64 h-64 bg-white/[0.02] blur-[80px] rounded-full pointer-events-none" />

                <motion.div variants={itemVars} className="flex flex-col items-center mb-10 text-center">
                    <div className="w-16 h-16 bg-white/[0.02] border border-white/10 rounded-2xl flex items-center justify-center mb-6 shadow-xl relative group overflow-hidden">
                        <div className="absolute inset-0 bg-[#22c55e]/10 opacity-0 group-hover:opacity-100 transition-opacity" />
                        <TrendingUp className="w-8 h-8 text-white relative z-10" />
                    </div>
                    <h2 className="text-3xl font-black text-white mb-2 tracking-tight">
                        {isSignup ? 'Create Account' : 'Welcome Back'}
                    </h2>
                    <p className="text-white/40 text-sm font-light mt-2 max-w-[250px] leading-relaxed">
                        {isSignup ? 'Sign up to get started with Study Stock.' : 'Log in to continue to your dashboard.'}
                    </p>
                </motion.div>

                <motion.form variants={itemVars} onSubmit={handleAuth} className="space-y-5">
                    {isSignup ? (
                        <>
                            <div>
                                <label className="block text-[10px] font-black uppercase tracking-widest text-white/40 mb-2 pl-1">Username</label>
                                <div className="relative">
                                    <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                                    <input
                                        type="text" value={username} onChange={(e) => setUsername(e.target.value)} required
                                        placeholder="trading_pro_99"
                                        className="w-full bg-white/[0.02] border border-white/5 rounded-2xl py-3.5 pl-11 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-white/20 focus:bg-white/[0.04] transition-all font-light"
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="block text-[10px] font-black uppercase tracking-widest text-white/40 mb-2 pl-1">Email Address</label>
                                <div className="relative">
                                    <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                                    <input
                                        type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                                        placeholder="you@server.com"
                                        className="w-full bg-white/[0.02] border border-white/5 rounded-2xl py-3.5 pl-11 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-white/20 focus:bg-white/[0.04] transition-all font-light"
                                    />
                                </div>
                            </div>
                        </>
                    ) : (
                        <div>
                            <label className="block text-[10px] font-black uppercase tracking-widest text-white/40 mb-2 pl-1">Email or Username</label>
                            <div className="relative">
                                <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                                <input
                                    type="text" value={loginIdentifier} onChange={(e) => setLoginIdentifier(e.target.value)} required
                                    placeholder="Username OR Email"
                                    className="w-full bg-white/[0.02] border border-white/5 rounded-2xl py-3.5 pl-11 pr-4 text-white placeholder:text-white/20 focus:outline-none focus:border-white/20 focus:bg-white/[0.04] transition-all font-light"
                                />
                            </div>
                        </div>
                    )}

                    <div>
                        <label className="block text-[10px] font-black uppercase tracking-widest text-white/40 mb-2 pl-1">Password</label>
                        <div className="relative">
                            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                            <input
                                type={showPassword ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} required
                                placeholder="••••••••"
                                className="w-full bg-white/[0.02] border border-white/5 rounded-2xl py-3.5 pl-11 pr-12 text-white placeholder:text-white/20 focus:outline-none focus:border-white/20 focus:bg-white/[0.04] transition-all font-light"
                            />
                            <button
                                type="button" onClick={() => setShowPassword(!showPassword)}
                                className="absolute right-4 top-1/2 -translate-y-1/2 text-white/30 hover:text-white transition-colors"
                            >
                                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                        </div>
                    </div>

                    {isSignup && (
                        <div>
                            <label className="block text-[10px] font-black uppercase tracking-widest text-white/40 mb-2 pl-1">Confirm Password</label>
                            <div className="relative">
                                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                                <input
                                    type={showPassword ? "text" : "password"} value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required
                                    placeholder="••••••••"
                                    className="w-full bg-white/[0.02] border border-white/5 rounded-2xl py-3.5 pl-11 pr-12 text-white placeholder:text-white/20 focus:outline-none focus:border-white/20 focus:bg-white/[0.04] transition-all font-light"
                                />
                            </div>
                        </div>
                    )}

                    {message && (
                        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
                            className={`p-4 rounded-2xl text-xs font-medium border ${message.type === 'success' ? 'bg-[#22c55e]/10 text-emerald-400 border-[#22c55e]/20' : 'bg-red-500/10 text-red-500 border-red-500/20 shadow-[0_0_15px_rgba(239,68,68,0.1)]'}`}
                        >
                            {message.text}
                        </motion.div>
                    )}

                    <button
                        type="submit" disabled={loading}
                        className="w-full bg-white text-black font-black py-4 rounded-xl transition-all uppercase tracking-widest text-sm hover:bg-gray-200 mt-6 flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(255,255,255,0.1)] disabled:opacity-50 disabled:cursor-not-allowed group relative overflow-hidden"
                    >
                        {loading ? (
                            <Loader2 className="w-5 h-5 animate-spin text-black" />
                        ) : (
                            <>
                                <span className="relative z-10">{isSignup ? 'Sign Up' : 'Log In'}</span>
                                <ArrowRight className="w-4 h-4 relative z-10 transition-transform group-hover:translate-x-1" />
                            </>
                        )}
                    </button>
                </motion.form>

                <motion.div variants={itemVars} className="mt-8 pt-8 border-t border-white/5 text-center text-xs font-bold uppercase tracking-widest text-white/30">
                    {isSignup ? 'Already have an account?' : "Don't have an account?"}{' '}
                    <button
                        type="button" onClick={() => onPageChange(isSignup ? 'login' : 'signup')}
                        className="text-white hover:text-[#22c55e] transition-colors ml-1 border-b border-transparent hover:border-[#22c55e] pb-0.5"
                    >
                        {isSignup ? 'Log In' : 'Sign Up'}
                    </button>
                </motion.div>
            </motion.div>
        </div>
    );
}
