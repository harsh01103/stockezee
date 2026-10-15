import { BookOpen, BarChart3, Shield, ArrowUpRight, Activity, PlayCircle, Star } from 'lucide-react';
import type { Page } from '@/App';
import { motion, useScroll, useTransform } from 'framer-motion';
import { useRef } from 'react';

interface HomePageProps {
  onPageChange: (page: Page) => void;
}

export function HomePage({ onPageChange }: HomePageProps) {
  const containerRef = useRef(null);
  const { scrollYProgress } = useScroll({ target: containerRef, offset: ["start start", "end start"] });

  const yBg = useTransform(scrollYProgress, [0, 1], ["0%", "50%"]);
  const opacityHero = useTransform(scrollYProgress, [0, 0.5], [1, 0]);

  // Graph starts drawing from the very first scroll down, completing before footer
  const drawProgress = useTransform(scrollYProgress, [0.05, 0.9], [0, 1]);
  // Fade out purely at the end of the page to vanish before the footer
  const graphOpacity = useTransform(scrollYProgress, [0, 0.7, 0.85], [0.8, 0.8, 0]);

  // STAGGER EFFECTS
  const containerVars: any = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.15, delayChildren: 0.3 } }
  };
  const itemVars: any = {
    hidden: { y: 50, opacity: 0 },
    show: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 12 } }
  };

  return (
    <div className="bg-[#050505] text-white relative" ref={containerRef}>

      {/* ── GLOBAL VIDEO BACKGROUND (z-0) ── */}
      <motion.div style={{ y: yBg }} className="absolute top-0 left-0 w-full h-[120vh] z-0 overflow-hidden pointer-events-none">
        <video
          autoPlay loop muted playsInline preload="auto"
          className="absolute inset-0 w-full h-full object-cover opacity-[0.4] mix-blend-screen mix-blend-luminosity scale-105"
        >
          {/* High motion abstract tunnel run video to simulate running forward */}
          <source src="https://cdn.pixabay.com/video/2019/11/24/29514-376518174_large.mp4" type="video/mp4" />
        </video>
        <div className="absolute inset-0 bg-gradient-to-t from-[#050505] via-transparent to-transparent" />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#050505]/40 to-[#050505]" />
        <div className="absolute inset-0 bg-gradient-to-r from-[#050505] via-transparent to-[#050505]" />

        <div className="absolute top-1/4 left-1/4 w-[50vw] h-[50vw] bg-emerald-500/10 blur-[120px] rounded-full mix-blend-screen animate-pulse duration-1000" />
        <div className="absolute bottom-1/4 right-1/4 w-[40vw] h-[40vw] bg-[#22c55e]/10 blur-[120px] rounded-full mix-blend-screen" />
      </motion.div>

      {/* ── ANIMATED GRAPH BACKGROUND (FIXED z-[5]) ── */}
      {/* Mapped strictly across the entire screen from 0% left to 100% right using viewBox percentages */}
      <motion.div style={{ opacity: graphOpacity }} className="fixed inset-0 w-full h-screen pointer-events-none z-[5] overflow-hidden mix-blend-screen">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 w-full h-full">
          <defs>
            <linearGradient id="trendGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#22c55e" stopOpacity="0" />
              <stop offset="5%" stopColor="#22c55e" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="1" />
            </linearGradient>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="1.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          {/* Main Glowing Trendline spanning full X-axis from 0 to 100 */}
          <motion.path
            d="M -5,80 L 10,85 L 25,60 L 40,65 L 55,30 L 75,50 L 90,-5 L 105,10"
            fill="none"
            stroke="url(#trendGradient)"
            strokeWidth="3"
            vectorEffect="non-scaling-stroke"
            filter="url(#glow)"
            style={{ pathLength: drawProgress }}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {/* Secondary Faint Indicator Line */}
          <motion.path
            d="M -5,83 C 15,90 20,60 35,60 C 50,60 60,40 80,40 C 90,40 95,15 105,15"
            fill="none"
            stroke="#22c55e"
            strokeWidth="1.5"
            vectorEffect="non-scaling-stroke"
            style={{ pathLength: drawProgress, opacity: 0.3 }}
            strokeDasharray="4 4"
          />
        </svg>
      </motion.div>

      {/* ─── Standard Scrolling Hero Text Foreground (z-10) ─── */}
      <section className="relative min-h-[85vh] flex items-center justify-center pt-24 pb-24 z-10 pointer-events-none">
        <div className="relative z-10 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pointer-events-auto">
          <motion.div
            variants={containerVars} initial="hidden" animate="show" style={{ opacity: opacityHero }}
            className="flex flex-col items-center text-center space-y-8"
          >
            <motion.div variants={itemVars} className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[#22c55e]/30 bg-[#22c55e]/10 backdrop-blur-md shadow-[0_0_20px_rgba(34,197,94,0.15)]">
              <span className="flex h-2 w-2 rounded-full bg-[#22c55e] animate-pulse" />
              <span className="text-[10px] md:text-xs font-bold text-emerald-300 uppercase tracking-widest">Simulate. Execute. Dominate.</span>
            </motion.div>

            <motion.h1 variants={itemVars} className="text-6xl sm:text-7xl lg:text-8xl font-black tracking-tighter leading-[0.9]">
              Outsmart the Market.<br />
              <span className="bg-gradient-to-r from-emerald-400 via-teal-300 to-[#22c55e] bg-clip-text text-transparent italic pr-2">Without Risk.</span>
            </motion.h1>

            <motion.p variants={itemVars} className="text-lg md:text-2xl text-white/50 max-w-2xl font-light">
              We analyzed millions of patterns to build the ultimate intraday simulation. Master institutional setups frame-by-frame.
            </motion.p>

            <motion.div variants={itemVars} className="flex flex-col sm:flex-row items-center gap-5 pt-8 z-50">
              <motion.button
                whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                onClick={() => onPageChange('learner')}
                className="relative group overflow-hidden bg-white text-black px-10 py-5 rounded-2xl font-black text-lg transition-all"
              >
                <div className="absolute inset-0 bg-gradient-to-r from-emerald-400 to-teal-400 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                <span className="relative flex items-center gap-2 group-hover:text-black">
                  Start Learning <ArrowUpRight className="w-6 h-6" />
                </span>
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                onClick={() => onPageChange('demo')}
                className="px-10 py-5 rounded-2xl font-bold text-lg text-white border border-white/10 hover:bg-white/5 backdrop-blur-md transition-all flex items-center gap-2 shadow-[0_0_20px_rgba(34,197,94,0.1)]"
              >
                <PlayCircle className="w-5 h-5 text-emerald-400" /> Try Demo Account
              </motion.button>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* ─── Glitchy Numbers / Stats Section ─── */}
      <section className="py-20 bg-transparent border-t border-white/5 relative z-10">
        <div className="absolute inset-0 bg-[#050505]/60 backdrop-blur-sm z-0" />
        <div className="max-w-7xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-8 divide-x divide-white/5 relative z-10">
          {[
            { n: '21K+', l: 'Instruments Scanned' },
            { n: '< 2ms', l: 'Execution Latency' },
            { n: '∞', l: 'Virtual Capital' },
            { n: '15+', l: 'Institutional Signals' }
          ].map((stat, i) => (
            <motion.div
              initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }}
              key={stat.l} className="text-center px-4"
            >
              <div className="text-4xl md:text-5xl font-black text-transparent bg-clip-text bg-gradient-to-br from-white to-white/30 mb-2">{stat.n}</div>
              <div className="text-[10px] uppercase tracking-widest text-white/40 font-bold">{stat.l}</div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ─── Features BENTO GRID ─── */}
      <section className="py-32 bg-[#050505]/40 backdrop-blur-sm relative z-10 mix-blend-screen overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }}
            className="text-center mb-20"
          >
            <h2 className="text-5xl lg:text-6xl font-black mb-6 tracking-tight">
              Built for <span className="text-emerald-400">HFT</span>-Level<br /> Market Analysis
            </h2>
            <p className="text-white/40 text-xl max-w-2xl mx-auto font-light">
              We don't use lagging indicators. Learn actual market structure, order flow patterns, and volume profiling.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                icon: BookOpen,
                title: 'Machine Learning Screener',
                description: 'Our proprietary V5 engine scans 21,000+ stocks in real-time, looking for Volatility Contraction Patterns (VCP) and Pocket Pivots.',
                span: 'md:col-span-2',
                bg: 'bg-gradient-to-br from-emerald-500/10 to-transparent border-[#22c55e]/20'
              },
              {
                icon: Activity,
                title: 'Live Paper Trading',
                description: 'Execute trades with zero latency. Test your strategies safely.',
                span: 'md:col-span-1',
                bg: 'bg-white/[0.02] border-white/10'
              },
              {
                icon: Shield,
                title: 'Institutional Grade Metrics',
                description: 'Relative Strength Ranking, Force Index, and Accumulation footprints that hedge funds use.',
                span: 'md:col-span-1',
                bg: 'bg-white/[0.02] border-white/10'
              },
              {
                icon: BarChart3,
                title: 'Data-Driven Autopsies',
                description: 'Every trade is logged. Review your exact entry/exit on the chart and figure out why a setup succeeded or failed.',
                span: 'md:col-span-2',
                bg: 'bg-gradient-to-br from-emerald-500/10 to-transparent border-emerald-500/20'
              },
            ].map((feature, i) => (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }} transition={{ delay: i * 0.1, duration: 0.5 }}
                key={feature.title}
                className={`group rounded-3xl p-10 border transition-all duration-500 hover:border-white/30 backdrop-blur-sm relative overflow-hidden ${feature.span} ${feature.bg}`}
              >
                <div className="absolute -right-20 -top-20 w-64 h-64 bg-white/5 rounded-full blur-3xl group-hover:bg-white/10 transition-colors duration-500" />
                <feature.icon className="w-10 h-10 text-white/80 mb-6" />
                <h3 className="text-2xl font-bold mb-4">{feature.title}</h3>
                <p className="text-lg text-white/50 leading-relaxed font-light">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Crazy Full Width Parallax Image / Video Banner ─── */}
      <section className="relative h-[60vh] flex items-center justify-center overflow-hidden border-y border-white/5">
        <div className="absolute inset-0 bg-emerald-950/20" />
        <video
          autoPlay loop muted playsInline
          className="absolute inset-0 w-full h-full object-cover mix-blend-overlay opacity-50"
        >
          <source src="https://cdn.pixabay.com/video/2019/11/24/29514-376518174_large.mp4" type="video/mp4" />
        </video>
        <div className="absolute inset-0 bg-gradient-to-b from-[#050505]/70 via-transparent to-[#050505]/70" />

        <motion.div
          initial={{ opacity: 0, y: 50 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
          className="relative z-10 text-center px-4"
        >
          <div className="w-20 h-20 mx-auto rounded-3xl bg-white flex items-center justify-center mb-8 rotate-12 hover:rotate-0 transition-transform duration-500 shadow-[0_0_50px_rgba(255,255,255,0.3)]">
            <Star className="w-10 h-10 text-black fill-black" />
          </div>
          <h2 className="text-4xl md:text-6xl font-black mb-4">Generate Your Edge.</h2>
          <p className="text-xl text-white/60">Built with modern tech. Designed for absolute precision.</p>
        </motion.div>
      </section>

      <section className="py-32 bg-transparent relative z-20 overflow-hidden mix-blend-screen border-t border-white/5">
        <div className="absolute inset-0 bg-[#050505]/60 backdrop-blur-md z-0" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[80vw] h-[80vw] bg-emerald-500/5 blur-[150px] rounded-full pointer-events-none" />
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
          <motion.h2
            initial={{ opacity: 0, scale: 0.9 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }}
            className="text-5xl lg:text-7xl font-black mb-8 tracking-tighter"
          >
            Stop guessing.<br />Start tracking.
          </motion.h2>
          <motion.div
            initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }}
            className="flex flex-col sm:flex-row justify-center gap-6"
          >
            <button
              onClick={() => onPageChange('demo')}
              className="bg-white text-black px-12 py-6 text-xl font-black rounded-full hover:bg-gray-200 transition-all hover:scale-105 active:scale-95 shadow-[0_0_40px_rgba(255,255,255,0.2)]"
            >
              Open Trading Terminal
            </button>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#050505] border-t border-white/10 pt-20 pb-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-12 mb-16">
            <div className="col-span-2 space-y-6">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-white rounded-xl flex items-center justify-center">
                  <BarChart3 className="w-6 h-6 text-black" />
                </div>
                <span className="text-2xl font-black tracking-tighter">Study Stock.</span>
              </div>
              <p className="text-white/40 text-sm max-w-sm leading-relaxed">
                The institutional-grade learning platform for ambitious intraday and swing traders. Powered by advanced algorithms.
              </p>
            </div>

            <div>
              <h4 className="font-bold mb-6 text-white uppercase tracking-widest text-xs">Platform</h4>
              <ul className="space-y-4">
                {[
                  { label: 'Home', page: 'home' },
                  { label: 'Learner', page: 'learner' },
                  { label: 'Demo', page: 'demo' },
                  { label: 'Global News', page: 'stock-news' },
                  { label: 'Trading Suggestions', page: 'suggestions' }
                ].map((item) => (
                  <li key={item.label}>
                    <button
                      onClick={() => {
                        if (item.page === 'home') {
                          window.scrollTo({ top: 0, behavior: 'smooth' });
                        }
                        onPageChange(item.page as Page);
                      }}
                      className="text-white/40 hover:text-white transition-colors duration-200 text-sm font-medium"
                    >
                      {item.label}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div className="pt-8 border-t border-white/5 text-center flex flex-col items-center">
            <p className="text-white/20 text-xs font-mono">
              © {new Date().getFullYear()} Study Stock Platform. All computational rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div >
  );
}
