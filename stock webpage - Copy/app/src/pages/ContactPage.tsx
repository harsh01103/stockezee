import { useState } from 'react';
import { Mail, Phone, MapPin, Send, ShieldAlert, Cpu } from 'lucide-react';
import { motion } from 'framer-motion';

export function ContactPage() {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    subject: '',
    message: ''
  });
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    setTimeout(() => {
      setSubmitted(false);
      setFormData({ name: '', email: '', subject: '', message: '' });
    }, 3000);
  };

  const containerVars = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.1 } }
  };

  const itemVars = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.6 } }
  };

  return (
    <div className="min-h-screen bg-[#050505] font-sans selection:bg-[#22c55e]/30">
      {/* Background Elements */}
      <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 right-1/4 w-[50vw] h-[50vw] bg-white/[0.015] blur-[150px] rounded-full mix-blend-screen" />
        <div className="absolute bottom-0 left-1/4 w-[40vw] h-[40vw] bg-[#22c55e]/5 blur-[120px] rounded-full mix-blend-screen" />
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.15] mix-blend-overlay pointer-events-none" />
      </div>

      <div className="relative z-10 max-w-[1400px] mx-auto px-6 py-12 pb-32">

        {/* Header */}
        <motion.div initial="hidden" animate="visible" variants={containerVars} className="mb-20">

          <motion.h1 variants={itemVars} className="text-4xl md:text-7xl font-black tracking-tighter mb-6 leading-tight">
            Initialize <span className="bg-gradient-to-r from-[#22c55e] to-emerald-300 bg-clip-text text-transparent">Contact</span>
          </motion.h1>
          <motion.p variants={itemVars} className="text-xl text-white/40 font-light max-w-2xl leading-relaxed mt-4">
            Direct secure channels to our infrastructure team. We prioritize technical issues and institutional inquiries.
          </motion.p>
        </motion.div>

        <div className="grid lg:grid-cols-12 gap-12 items-start">

          {/* Left panel */}
          <motion.div
            initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6 }}
            className="lg:col-span-4 space-y-6"
          >
            {[
              { icon: Mail, label: 'Secure Email', value: 'support@studystock.com', sub: '24h SLA response time' },
              { icon: Phone, label: 'Direct Line', value: '+91 8904435530', sub: '0900 - 1800 IST' },
              { icon: MapPin, label: 'Mainframe Location', value: 'VIT CHENNAI', sub: 'Tamil Nadu 600013' },
            ].map((info, i) => (
              <div key={i} className="p-6 rounded-3xl bg-white/[0.01] border border-white/5 hover:border-white/10 transition-colors flex items-start gap-5 group">
                <div className="w-12 h-12 rounded-2xl bg-white/[0.02] border border-white/5 flex items-center justify-center shrink-0 group-hover:bg-[#22c55e]/10 transition-colors">
                  <info.icon className="w-5 h-5 text-white/40 group-hover:text-[#22c55e] transition-colors" />
                </div>
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-widest text-[#22c55e] mb-1">{info.label}</div>
                  <div className="text-lg font-black text-white/90 mb-0.5">{info.value}</div>
                  <div className="text-[11px] text-white/40 tracking-wider uppercase font-medium">{info.sub}</div>
                </div>
              </div>
            ))}

            <div className="p-6 rounded-3xl bg-[#0a0a0a] border border-white/5 mt-8">
              <h3 className="text-xs font-black uppercase tracking-widest text-white/30 mb-4">Network Status</h3>
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-[#22c55e] shadow-[0_0_10px_rgba(34,197,94,0.5)] animate-pulse" />
                <span className="text-sm font-bold text-white/80">All Systems Operational</span>
              </div>
              <div className="text-[10px] text-white/40 uppercase tracking-widest mt-2">Latency: 14ms (Mumbai)</div>
            </div>
          </motion.div>

          {/* Right form */}
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.6, delay: 0.1 }}
            className="lg:col-span-8"
          >
            <div className="bg-[#0a0a0a] rounded-3xl p-8 md:p-12 border border-white/5 relative overflow-hidden shadow-2xl">
              <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 blur-[100px] rounded-full pointer-events-none" />

              {submitted ? (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-20 relative z-10">
                  <div className="w-20 h-20 bg-[#22c55e]/10 border border-[#22c55e]/20 rounded-full flex items-center justify-center mx-auto mb-6">
                    <Cpu className="w-10 h-10 text-[#22c55e]" />
                  </div>
                  <h3 className="text-2xl font-black mb-3 text-white">Transmission Successful</h3>
                  <p className="text-white/40 font-light max-w-sm mx-auto">Your query has been added to our queue and will be processed immediately.</p>
                </motion.div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-6 relative z-10">
                  <div className="grid sm:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <label className="text-[10px] font-black tracking-widest uppercase text-white/50">Identifier</label>
                      <input
                        type="text" required
                        value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        className="w-full bg-white/[0.02] border border-white/5 rounded-2xl px-5 py-4 text-white focus:outline-none focus:border-[#22c55e]/50 focus:bg-white/[0.04] transition-all font-light"
                        placeholder="Your Name"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[10px] font-black tracking-widest uppercase text-white/50">Return Address</label>
                      <input
                        type="email" required
                        value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        className="w-full bg-white/[0.02] border border-white/5 rounded-2xl px-5 py-4 text-white focus:outline-none focus:border-[#22c55e]/50 focus:bg-white/[0.04] transition-all font-light"
                        placeholder="name@server.com"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-black tracking-widest uppercase text-white/50">Classification</label>
                    <input
                      type="text" required
                      value={formData.subject} onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
                      className="w-full bg-white/[0.02] border border-white/5 rounded-2xl px-5 py-4 text-white focus:outline-none focus:border-[#22c55e]/50 focus:bg-white/[0.04] transition-all font-light"
                      placeholder="Subject of inquiry"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-black tracking-widest uppercase text-white/50">Data Payload</label>
                    <textarea
                      required
                      value={formData.message} onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                      className="w-full bg-white/[0.02] border border-white/5 rounded-2xl px-5 py-4 text-white focus:outline-none focus:border-[#22c55e]/50 focus:bg-white/[0.04] transition-all min-h-[160px] resize-y font-light"
                      placeholder="Describe your issue or inquiry in detail..."
                    />
                  </div>

                  <button type="submit" className="w-full bg-white text-black font-black py-4 rounded-xl flex items-center justify-center gap-2 hover:bg-gray-200 transition-all uppercase tracking-widest mt-4">
                    <Send className="w-4 h-4" /> Transmit Request
                  </button>
                  <p className="text-[10px] text-white/30 text-center uppercase tracking-widest font-bold mt-4 flex items-center justify-center gap-2"><ShieldAlert className="w-3 h-3" /> End-to-end encrypted connection</p>
                </form>
              )}
            </div>
          </motion.div>

        </div>
      </div>
    </div>
  );
}
