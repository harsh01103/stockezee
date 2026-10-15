import { useEffect, useState } from 'react';
import { BarChart3, BookOpen, Building2, FileText, Link2, Search, ShieldAlert, TrendingUp } from 'lucide-react';
import { motion } from 'framer-motion';

interface CompanyDocument {
  id?: string;
  title?: string | null;
  url?: string | null;
  type?: string | null;
  origin_type?: string | null;
  source_name?: string | null;
  published_at?: string | null;
  content_quality?: number | null;
  retrieval_score?: number | null;
}

interface DocIntel {
  id?: string;
  symbol: string;
  document_type: string;
  filing_date: string;
  sentiment_score: number;
  risk_factors: string[];
  growth_catalysts: string[];
  guidance?: string;
  capex_trend: string;
  management_tone: string;
  confidence: string | null;
  evidence: string | null;
  retrieval_score: number | null;
  company_documents?: CompanyDocument | CompanyDocument[] | null;
  document?: CompanyDocument | null;
}

interface IntelApiResponse {
  symbol: string;
  cache: 'hit' | 'miss';
  stages: string[];
  documents_found: number;
  fetch_failed?: boolean;
  results: DocIntel[];
}

const progressStages = ['Searching...', 'Fetching documents...', 'Parsing...', 'Ranking...'];

export function CompanyIntelPanel() {
  const [intelData, setIntelData] = useState<DocIntel | null>(null);
  const [symbol, setSymbol] = useState('RELIANCE');
  const [inputVal, setInputVal] = useState('RELIANCE');
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState(progressStages[0]);
  const [errorText, setErrorText] = useState('');
  const [fetchFailed, setFetchFailed] = useState(false);

  const normalizeList = (value: unknown): string[] => {
    if (Array.isArray(value)) return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
    return [];
  };

  const selectedDocument = (() => {
    if (intelData?.document) return intelData.document;
    if (Array.isArray(intelData?.company_documents)) return intelData?.company_documents[0] || null;
    return intelData?.company_documents || null;
  })();

  const sourceText = selectedDocument?.url || selectedDocument?.title || intelData?.evidence || '';
  const sourceLabel = (() => {
    if (!sourceText.startsWith('http')) return sourceText;
    try {
      return new URL(sourceText).hostname.replace(/^www\./, '');
    } catch {
      return sourceText;
    }
  })();
  const topEvidence = intelData?.evidence || selectedDocument?.title || selectedDocument?.url || 'Fetch completed without ranked evidence.';

  const fetchIntel = async (sym: string) => {
    setLoading(true);
    setIntelData(null);
    setErrorText('');
    setFetchFailed(false);
    setStage(progressStages[0]);

    const timers = progressStages.slice(1).map((nextStage, index) => (
      window.setTimeout(() => setStage(nextStage), 350 + index * 450)
    ));

    try {
      const response = await fetch(`/api/intel?symbol=${encodeURIComponent(sym)}`);
      const payload = await response.json() as IntelApiResponse | { error?: string };

      if (!response.ok || ('error' in payload && payload.error)) {
        throw new Error(('error' in payload && payload.error) || 'Document intelligence fetch failed.');
      }

      const intelPayload = payload as IntelApiResponse;
      setStage('Done');
      const topRow = intelPayload.results?.[0];

      if (!topRow) {
        setFetchFailed(Boolean(intelPayload.fetch_failed));
        return;
      }

      setIntelData({
        ...topRow,
        risk_factors: normalizeList(topRow.risk_factors),
        growth_catalysts: normalizeList(topRow.growth_catalysts)
      });
    } catch (error) {
      setFetchFailed(true);
      setErrorText(error instanceof Error ? error.message : 'Document intelligence fetch failed.');
    } finally {
      timers.forEach(timer => window.clearTimeout(timer));
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIntel(symbol);
  }, [symbol]);

  const handleSearch = (event: React.FormEvent) => {
    event.preventDefault();
    if (inputVal.trim()) setSymbol(inputVal.trim().toUpperCase());
  };

  return (
    <div className="bg-[#0a0a0a] rounded-3xl border border-white/10 shadow-2xl p-6 lg:p-8 relative overflow-hidden">
      <div className="absolute top-0 right-0 w-64 h-64 bg-sky-500/10 blur-[100px] rounded-full pointer-events-none" />

      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 mb-8 relative z-10">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center">
            <Building2 className="w-6 h-6 text-sky-400" />
          </div>
          <div>
            <h2 className="text-2xl font-black text-white tracking-tight uppercase">Company Intelligence</h2>
            <p className="text-xs text-white/40 font-bold tracking-widest uppercase mt-1">Fetch-First Document Analysis Pipeline</p>
          </div>
        </div>

        <form onSubmit={handleSearch} className="flex items-center gap-2 w-full md:w-auto">
          <div className="relative flex-1 md:w-64">
            <Search className="w-4 h-4 text-white/40 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search symbol..."
              value={inputVal}
              onChange={event => setInputVal(event.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-xl py-2 pl-10 pr-4 text-sm text-white placeholder-white/30 focus:outline-none focus:border-sky-500/50 transition-colors uppercase font-bold"
            />
          </div>
          <button type="submit" className="bg-sky-500 text-white px-4 py-2 rounded-xl text-sm font-bold uppercase tracking-widest hover:bg-sky-600 transition-colors">
            Scan
          </button>
        </form>
      </div>

      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-4">
          <div className="w-12 h-12 border-4 border-sky-500/20 border-t-sky-500 rounded-full animate-spin" />
          <div className="text-white/40 text-xs font-mono uppercase tracking-widest">{stage}</div>
        </div>
      ) : !intelData ? (
        <div className="py-20 text-center">
          <div className="text-white text-sm font-black tracking-widest">
            {fetchFailed ? 'NO VERIFIED DOCUMENTS' : 'Searching...'}
          </div>
          <div className="text-white/40 text-xs mt-3 max-w-xl mx-auto">
            {errorText || (fetchFailed ? `Document fetch failed for ${symbol}.` : 'Fetching documents...')}
          </div>
        </div>
      ) : (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6 relative z-10">
          <div className="flex items-center gap-4 border-b border-white/5 pb-6">
            <h3 className="text-4xl font-black text-white tracking-tighter">{intelData.symbol}</h3>
            <span className="px-3 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-white/60">
              {intelData.document_type}
            </span>
            <span className="text-xs text-white/40 font-medium">Filed: {intelData.filing_date}</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <BarChart3 className="w-4 h-4 text-sky-400" />
                <span className="text-[10px] text-white/40 font-bold uppercase tracking-widest">Sentiment</span>
              </div>
              <div className="text-3xl font-black text-sky-400">{intelData.sentiment_score}/100</div>
            </div>

            <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <BookOpen className="w-4 h-4 text-white/40" />
                <span className="text-[10px] text-white/40 font-bold uppercase tracking-widest">Tone</span>
              </div>
              <div className="text-xl font-black text-white uppercase tracking-wider">{intelData.management_tone}</div>
            </div>

            <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <TrendingUp className="w-4 h-4 text-white/40" />
                <span className="text-[10px] text-white/40 font-bold uppercase tracking-widest">CapEx</span>
              </div>
              <div className="text-xl font-black text-white uppercase tracking-wider">{intelData.capex_trend}</div>
            </div>

            <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <FileText className="w-4 h-4 text-white/40" />
                <span className="text-[10px] text-white/40 font-bold uppercase tracking-widest">Confidence</span>
              </div>
              <div className="text-xl font-black text-white uppercase tracking-wider">{intelData.confidence || 'LOW'}</div>
              <div className="text-[10px] text-white/30 font-mono mt-1">Score: {intelData.retrieval_score ?? 0}</div>
            </div>
          </div>

          <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-5">
            <div className="flex items-center gap-2 border-b border-white/5 pb-2 mb-4">
              <Link2 className="w-4 h-4 text-sky-400" />
              <h4 className="text-xs font-bold text-sky-400 uppercase tracking-widest">Evidence Mode</h4>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-[10px] text-white/35 font-bold uppercase tracking-widest mb-1">Document Type</div>
                <div className="text-white/80">{selectedDocument?.origin_type || intelData.document_type}</div>
              </div>
              <div>
                <div className="text-[10px] text-white/35 font-bold uppercase tracking-widest mb-1">Published Date</div>
                <div className="text-white/80">{selectedDocument?.published_at?.split('T')[0] || intelData.filing_date}</div>
              </div>
              <div>
                <div className="text-[10px] text-white/35 font-bold uppercase tracking-widest mb-1">Source</div>
                <div className="text-white/80 break-words">{sourceLabel || 'Fetch completed without source metadata.'}</div>
              </div>
              <div>
                <div className="text-[10px] text-white/35 font-bold uppercase tracking-widest mb-1">Confidence</div>
                <div className="text-white/80">{intelData.confidence || 'LOW'}</div>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-white/5">
              <div className="text-[10px] text-white/35 font-bold uppercase tracking-widest mb-1">Top Evidence</div>
              <div className="text-sm text-white/70 break-words">{topEvidence}</div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4">
            <div className="space-y-3">
              <div className="flex items-center gap-2 border-b border-white/5 pb-2">
                <TrendingUp className="w-4 h-4 text-[#22c55e]" />
                <h4 className="text-xs font-bold text-[#22c55e] uppercase tracking-widest">Growth</h4>
              </div>
              <ul className="space-y-2">
                {intelData.growth_catalysts.length > 0 ? intelData.growth_catalysts.map((catalyst, index) => (
                  <li key={index} className="flex items-start gap-2 text-sm text-white/70">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e]/50 mt-1.5 flex-shrink-0" />
                    {catalyst}
                  </li>
                )) : <li className="text-sm text-white/40">No growth evidence extracted from fetched documents.</li>}
              </ul>
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-2 border-b border-white/5 pb-2">
                <ShieldAlert className="w-4 h-4 text-red-500" />
                <h4 className="text-xs font-bold text-red-500 uppercase tracking-widest">Risk</h4>
              </div>
              <ul className="space-y-2">
                {intelData.risk_factors.length > 0 ? intelData.risk_factors.map((risk, index) => (
                  <li key={index} className="flex items-start gap-2 text-sm text-white/70">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-500/50 mt-1.5 flex-shrink-0" />
                    {risk}
                  </li>
                )) : <li className="text-sm text-white/40">No risk evidence extracted from fetched documents.</li>}
              </ul>
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-2 border-b border-white/5 pb-2">
                <BookOpen className="w-4 h-4 text-sky-400" />
                <h4 className="text-xs font-bold text-sky-400 uppercase tracking-widest">Guidance</h4>
              </div>
              <p className="text-sm text-white/70">{intelData.guidance || 'No explicit guidance extracted from fetched documents.'}</p>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}
