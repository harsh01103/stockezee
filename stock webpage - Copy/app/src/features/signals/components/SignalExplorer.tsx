import { useEffect, useState } from 'react';
import { RefreshCw, Database } from 'lucide-react';

interface PersistedSignal {
  id: string;
  symbol: string;
  type: string;
  direction: string;
  confidence: number;
  price_at_signal: number;
  timeframe: string;
  created_at: string;
}

export function SignalExplorer() {
  const [signals, setSignals] = useState<PersistedSignal[]>([]);
  const [loading, setLoading] = useState(false);

  // In a real app, this would fetch from /api/signals
  // Here we mock the database fetch matching signalLogger output
  const fetchSignals = async () => {
    setLoading(true);
    try {
      // Mocked data since backend API route isn't fully linked
      const mockData: PersistedSignal[] = [
        { id: '1', symbol: 'RELIANCE', type: 'VCP_BREAKOUT', direction: 'BULLISH', confidence: 92.0, price_at_signal: 2500, timeframe: '1W', created_at: new Date().toISOString() },
        { id: '2', symbol: 'HDFCBANK', type: 'MOMENTUM_BURST', direction: 'BEARISH', confidence: 85.5, price_at_signal: 1500, timeframe: '1D', created_at: new Date(Date.now() - 86400000).toISOString() },
      ];
      setSignals(mockData);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchSignals();
  }, []);

  return (
    <div className="bg-[#0a0a0a] rounded-3xl border border-white/10 overflow-hidden shadow-2xl p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Database className="w-5 h-5 text-[#22c55e]" />
          <h2 className="text-xl font-black text-white tracking-tight uppercase">Signal Registry Explorer</h2>
        </div>
        <button onClick={fetchSignals} className="p-2 rounded-xl border border-white/10 text-white/40 hover:text-white transition-colors">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-white/10 text-[10px] uppercase tracking-widest text-white/40">
              <th className="pb-3 pr-4 font-bold">Time</th>
              <th className="pb-3 pr-4 font-bold">Symbol</th>
              <th className="pb-3 pr-4 font-bold">Signal Type</th>
              <th className="pb-3 pr-4 font-bold">Direction</th>
              <th className="pb-3 pr-4 font-bold">Confidence</th>
              <th className="pb-3 pr-4 font-bold">Price @ Signal</th>
            </tr>
          </thead>
          <tbody>
            {signals.map(s => (
              <tr key={s.id} className="border-b border-white/5 hover:bg-white/[0.02] transition-colors">
                <td className="py-4 pr-4 text-xs text-white/60">{new Date(s.created_at).toLocaleString('en-IN')}</td>
                <td className="py-4 pr-4 text-sm font-bold text-white">{s.symbol}</td>
                <td className="py-4 pr-4 text-xs font-mono text-white/80">{s.type}</td>
                <td className="py-4 pr-4">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-widest ${s.direction === 'BULLISH' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                    {s.direction}
                  </span>
                </td>
                <td className="py-4 pr-4 text-sm font-bold text-white">{s.confidence}%</td>
                <td className="py-4 pr-4 text-sm font-bold text-white">₹{s.price_at_signal}</td>
              </tr>
            ))}
            {signals.length === 0 && !loading && (
              <tr>
                <td colSpan={6} className="py-8 text-center text-sm text-white/40">No signals registered yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
