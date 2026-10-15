import { useState } from 'react';
import { Play, Pause, SkipForward, Rewind, BarChart2, Calendar, Search } from 'lucide-react';
import { motion } from 'framer-motion';

export function ReplayMode() {
    const [isPlaying, setIsPlaying] = useState(false);
    const [progress, setProgress] = useState(0);

    const togglePlay = () => setIsPlaying(!isPlaying);

    return (
        <div className="bg-[#0a0a0a] rounded-3xl border border-white/10 shadow-2xl p-6 lg:p-8 relative overflow-hidden flex flex-col h-[70vh]">
            <div className="absolute top-0 right-0 w-64 h-64 bg-purple-500/10 blur-[100px] rounded-full pointer-events-none" />

            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 mb-8 relative z-10">
                <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center">
                        <Play className="w-6 h-6 text-purple-400 ml-1" />
                    </div>
                    <div>
                        <h2 className="text-2xl font-black text-white tracking-tight uppercase">Trade Replay System</h2>
                        <p className="text-xs text-white/40 font-bold tracking-widest uppercase mt-1">Historical Minute-by-Minute Simulation</p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <div className="relative">
                        <Search className="w-4 h-4 text-white/40 absolute left-3 top-1/2 -translate-y-1/2" />
                        <input
                            type="text"
                            placeholder="Session ID or Symbol..."
                            className="w-full md:w-64 bg-white/5 border border-white/10 rounded-xl py-2 pl-10 pr-4 text-sm text-white placeholder-white/30 focus:outline-none focus:border-purple-500/50 transition-colors uppercase font-bold"
                        />
                    </div>
                    <button className="bg-white/5 border border-white/10 text-white p-2 rounded-xl hover:bg-white/10 transition-colors">
                        <Calendar className="w-4 h-4" />
                    </button>
                </div>
            </div>

            <div className="flex-1 flex flex-col items-center justify-center border border-dashed border-white/10 rounded-2xl bg-white/[0.01] relative z-10 mb-6 relative overflow-hidden">
                <BarChart2 className="w-24 h-24 text-white/5 absolute" />
                <div className="text-center z-10">
                    <h3 className="text-xl font-bold text-white tracking-wider mb-2">RELIANCE - SEP 15, 2023</h3>
                    <p className="text-white/40 text-sm font-mono">10:15 AM (Replay Mode Active)</p>
                </div>
            </div>

            <div className="relative z-10 bg-white/[0.02] border border-white/5 rounded-2xl p-6">
                <div className="flex items-center justify-between mb-4">
                    <div className="text-xs font-mono text-white/50">09:15 AM</div>
                    <div className="text-xs font-mono text-white/50">03:30 PM</div>
                </div>
                
                <div className="h-2 bg-white/10 rounded-full overflow-hidden mb-6 relative cursor-pointer" onClick={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    setProgress(Math.max(0, Math.min(100, (x / rect.width) * 100)));
                }}>
                    <motion.div 
                        className="h-full bg-purple-500 shadow-[0_0_10px_rgba(168,85,247,0.5)]" 
                        animate={{ width: `${progress}%` }} 
                        transition={{ duration: 0.1 }}
                    />
                </div>

                <div className="flex items-center justify-center gap-6">
                    <button className="text-white/40 hover:text-white transition-colors" onClick={() => setProgress(Math.max(0, progress - 10))}>
                        <Rewind className="w-6 h-6" />
                    </button>
                    <button 
                        onClick={togglePlay}
                        className="w-14 h-14 rounded-full bg-purple-500 text-white flex items-center justify-center hover:bg-purple-600 transition-colors shadow-[0_0_20px_rgba(168,85,247,0.3)]"
                    >
                        {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6 ml-1" />}
                    </button>
                    <button className="text-white/40 hover:text-white transition-colors" onClick={() => setProgress(Math.min(100, progress + 10))}>
                        <SkipForward className="w-6 h-6" />
                    </button>
                </div>
            </div>
        </div>
    );
}
