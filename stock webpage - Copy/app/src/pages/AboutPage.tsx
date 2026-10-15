import { Users, TrendingUp, Shield, Activity, ArrowUpRight } from 'lucide-react';
import { motion } from 'framer-motion';

interface AboutPageProps {
  onPageChange?: (page: any) => void;
}

export function AboutPage({ onPageChange }: AboutPageProps) {
  const containerVars = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.1 }
    }
  };

  const itemVars: any = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } }
  };

  return (
    <div className="min-h-screen bg-[#050505] font-sans selection:bg-[#22c55e]/30">
      {/* Background Elements */}
      <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 right-1/4 w-[50vw] h-[50vw] bg-white/[0.015] blur-[150px] rounded-full mix-blend-screen" />
        <div className="absolute bottom-0 left-1/4 w-[40vw] h-[40vw] bg-[#22c55e]/5 blur-[120px] rounded-full mix-blend-screen" />
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.15] mix-blend-overlay pointer-events-none" />
      </div>

      <div className="relative z-10">
        {/* Hero Section */}
        <section className="pt-16 pb-20 overflow-hidden">
          <div className="max-w-[1400px] mx-auto px-6">
            <motion.div
              initial="hidden" animate="visible" variants={containerVars}
              className="text-center max-w-4xl mx-auto"
            >

              <motion.h1 variants={itemVars} className="text-5xl md:text-7xl font-black tracking-tighter mb-8 leading-[1.1]">
                Institutional Edge for the <br />
                <span className="bg-gradient-to-r from-[#22c55e] to-emerald-300 bg-clip-text text-transparent">Everyday Trader</span>
              </motion.h1>
              <motion.p variants={itemVars} className="text-xl text-white/50 font-light leading-relaxed max-w-2xl mx-auto">
                We're on a mission to democratize elite quantitative analysis. Moving beyond retail speculation, we provide the infrastructure needed for precise, systematic, and risk-adjusted market participation.
              </motion.p>
            </motion.div>
          </div>
        </section>

        {/* Stats Grid */}
        <section className="py-12 border-y border-white/5 bg-white/[0.01]">
          <div className="max-w-[1400px] mx-auto px-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8 divide-x divide-white/5">
              {[
                { value: '10,000+', label: 'Active Learners' },
                { value: '50+', label: 'Interactive Lessons' },
                { value: '95%', label: 'Risk Protection' },
                { value: '24/7', label: 'Quant Simulation' },
              ].map((stat, i) => (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }}
                  key={stat.label} className="text-center px-4"
                >
                  <p className="text-4xl md:text-5xl font-black text-white mb-2 tracking-tighter">{stat.value}</p>
                  <p className="text-[10px] text-white/40 uppercase tracking-widest font-bold">{stat.label}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* Values Section */}
        <section className="py-24">
          <div className="max-w-[1400px] mx-auto px-6">
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-4xl font-black tracking-tight mb-4">Core Philosophy</h2>
            </div>
            <div className="grid md:grid-cols-3 gap-6">
              {[
                {
                  icon: Activity,
                  title: 'Edge Over Emotion',
                  description: 'Trading is a mathematical pursuit. We prioritize statistical advantages and systematic execution over gut feelings.',
                },
                {
                  icon: Shield,
                  title: 'Capital Preservation First',
                  description: 'The foundation of alpha begins with defending what you have. We build robust risk parameters into everything.',
                },
                {
                  icon: Users,
                  title: 'Uncompromising Education',
                  description: 'We do not sell signals. We build the infrastructure to forge independent, fully self-sufficient systematic traders.',
                },
              ].map((value, i) => (
                <motion.div
                  initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }}
                  key={value.title}
                  className="bg-white/[0.02] border border-white/5 rounded-3xl hover:bg-white/[0.04] transition-colors group"
                >
                  <button onClick={() => onPageChange && onPageChange('learner')} className="px-10 py-5 rounded-2xl font-bold text-lg text-white border border-white/10 hover:bg-white/5 backdrop-blur-md transition-all w-full h-full text-left">
                    <div className="w-14 h-14 bg-white/[0.05] rounded-2xl flex items-center justify-center mb-8 group-hover:bg-[#22c55e]/10 group-hover:text-[#22c55e] text-white transition-colors">
                      <value.icon className="w-6 h-6" />
                    </div>
                    <h3 className="text-xl font-bold mb-4 tracking-tight">{value.title}</h3>
                    <p className="text-white/40 font-light leading-relaxed">{value.description}</p>
                  </button>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* What We Offer / Features */}
        <section className="py-24 bg-[#0a0a0a] border-y border-white/5 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-96 h-96 bg-[#22c55e]/5 blur-[150px] rounded-full" />
          <div className="relative max-w-[1400px] mx-auto px-6">
            <div className="flex flex-col md:flex-row justify-between items-end mb-16 gap-6">
              <div className="max-w-xl">
                <h2 className="text-3xl md:text-5xl font-black tracking-tight mb-6">The Platform Architecture</h2>
                <p className="text-white/40 text-lg font-light">Comprehensive infrastructure engineered strictly for achieving a measurable market edge.</p>
              </div>
              <button className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-white/50 hover:text-white transition-colors pb-2 border-b border-transparent hover:border-white">
                Explore The Terminal <ArrowUpRight className="w-4 h-4" />
              </button>
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              {[
                {
                  title: 'Advanced Systematic Screeners',
                  description: 'Scan thousands of securities instantly utilizing deep quantitative algorithms that analyze volume profiles and institutional accumulation.',
                },
                {
                  title: 'Zero-Risk Execution Engine',
                  description: 'State-of-the-art paper trading terminal that mirrors exact live market slippage, spread, and fast-market volatility.',
                },
                {
                  title: 'Order Flow & Candlestick Modeling',
                  description: 'Learn to read naked price action and the psychology behind structural candles through our premium Academy modules.',
                },
                {
                  title: 'Confluence Aggregation Panels',
                  description: 'Stop guessing. Use mathematical confluence from over 15 proprietary indicators to generate extreme-probability setups.',
                },
              ].map((item, index) => (
                <motion.div
                  initial={{ opacity: 0, x: index % 2 === 0 ? -20 : 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}
                  key={item.title}
                  className="flex gap-6 p-8 bg-white/[0.01] border border-white/5 rounded-3xl hover:border-white/10 transition-colors"
                >
                  <div className="text-3xl font-black text-white/10 shrink-0">
                    0{index + 1}
                  </div>
                  <div>
                    <h3 className="font-bold text-lg mb-2 tracking-tight">{item.title}</h3>
                    <p className="text-white/40 font-light leading-relaxed text-sm">{item.description}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* Footer CTA */}
        <section className="py-32 text-center">
          <div className="max-w-2xl mx-auto px-6">
            <h2 className="text-4xl font-black tracking-tighter mb-6 text-white">Stop Gambling.<br />Start Executing systematically.</h2>
            <p className="text-white/40 font-light mb-10">Sign up and gain access to the complete terminal, screener, and academy instantly.</p>
            <button onClick={() => onPageChange && onPageChange('demo')} className="relative group overflow-hidden bg-[#22c55e] text-black px-10 py-5 rounded-2xl font-black text-lg transition-all scale-105">
              Initialize Platform
            </button>
          </div>
        </section>

        {/* Simple Footer Base */}
        <footer className="bg-[#050505] border-t border-white/5 py-12">
          <div className="max-w-[1400px] mx-auto px-6 text-center flex flex-col items-center">
            <div className="flex items-center gap-2 mb-6 opacity-50">
              <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-black" />
              </div>
              <span className="text-xl font-bold text-white">Study Stock</span>
            </div>
            <p className="text-xs text-white/20 uppercase tracking-widest font-bold">© {new Date().getFullYear()} Study Stock Quant Infrastructure. All rights reserved.</p>
          </div>
        </footer>
      </div>
    </div>
  );
}
