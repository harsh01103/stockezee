import { useEffect, useMemo, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { useAuth } from "@/context/AuthProvider";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { OptionsSearch } from "@/features/options/components/OptionsSearch";
import { OptionsChainTable } from "@/features/options/components/OptionsChainTable";
import { StrikeDetailSheet } from "@/features/options/components/StrikeDetailSheet";
import { OptionsAnalyticsPanel } from "@/features/options/components/OptionsAnalyticsPanel";
import { OptionsChartPanel } from "@/features/options/components/OptionsChartPanel";
import { OptionChartModal } from "@/features/options/components/OptionChartModal";
import { OptionsWatchlistPanel } from "@/features/options/components/OptionsWatchlistPanel";
import { OptionsOrderModal } from "@/features/options/components/OptionsOrderModal";
import { OptionsPositionsPanel } from "@/features/options/components/OptionsPositionsPanel";
import { optionsApi } from "@/features/options/services/optionsApi";
import { optionsPersistence } from "@/features/options/services/optionsPersistence";
import type { LtpRow } from "@/features/options/services/optionsApi";
import type {
  AnalyticsResponse,
  ChainFilters,
  ChartCandle,
  DashboardResponse,
  OptionChainRow,
  OptionChainResponse,
  OptionUnderlying,
  PaperPosition,
  UpstoxStatus,
  WatchlistItem,
} from "@/features/options/types";

const DEFAULT_FILTERS: ChainFilters = {
  strikeCount: 31,
  moneyness: "ALL",
  minLiquidity: 0,
  strikeQuery: "",
  autoRefresh: true,
};

const DEFAULT_UNDERLYING: OptionUnderlying = {
  symbol: "NIFTY",
  name: "NIFTY 50",
  kind: "index",
  quoteSymbol: "^NSEI",
  exchange: "NSE_INDEX",
  strikeStep: 50,
  lotSize: 65,
  basePrice: 24850,
};

function toneForChange(value: number) {
  return value >= 0 ? "text-emerald-400" : "text-red-400";
}

/**
 * Merge LTP tick data into existing chain rows in-place.
 */
function mergeChainLtp(
  existingRows: OptionChainRow[],
  ltpRows: LtpRow[]
): OptionChainRow[] {
  const ltpMap = new Map<number, LtpRow>();
  for (const row of ltpRows) {
    ltpMap.set(row.strike, row);
  }

  let anyChanged = false;
  const merged = existingRows.map((row) => {
    const ltp = ltpMap.get(row.strike);
    if (!ltp) return row;

    const callLtpChanged = row.call.ltp !== ltp.callLtp;
    const callBidChanged = row.call.bid !== ltp.callBid;
    const callAskChanged = row.call.ask !== ltp.callAsk;
    const putLtpChanged = row.put.ltp !== ltp.putLtp;
    const putBidChanged = row.put.bid !== ltp.putBid;
    const putAskChanged = row.put.ask !== ltp.putAsk;

    if (!callLtpChanged && !callBidChanged && !callAskChanged && !putLtpChanged && !putBidChanged && !putAskChanged) {
      return row;
    }

    anyChanged = true;

    const callChange = ltp.callClosePrice ? ltp.callLtp - ltp.callClosePrice : row.call.change;
    const callChangePercent = ltp.callClosePrice ? ((ltp.callLtp - ltp.callClosePrice) / ltp.callClosePrice) * 100 : row.call.changePercent;
    const putChange = ltp.putClosePrice ? ltp.putLtp - ltp.putClosePrice : row.put.change;
    const putChangePercent = ltp.putClosePrice ? ((ltp.putLtp - ltp.putClosePrice) / ltp.putClosePrice) * 100 : row.put.changePercent;

    return {
      ...row,
      call: {
        ...row.call,
        ltp: ltp.callLtp,
        bid: ltp.callBid,
        ask: ltp.callAsk,
        change: callChange,
        changePercent: callChangePercent,
        spread: Number((ltp.callAsk - ltp.callBid).toFixed(2)),
      },
      put: {
        ...row.put,
        ltp: ltp.putLtp,
        bid: ltp.putBid,
        ask: ltp.putAsk,
        change: putChange,
        changePercent: putChangePercent,
        spread: Number((ltp.putAsk - ltp.putBid).toFixed(2)),
      },
    };
  });

  return anyChanged ? merged : existingRows;
}

export function OptionsPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState("chain");
  const [selectedUnderlying, setSelectedUnderlying] = useState<OptionUnderlying | null>(DEFAULT_UNDERLYING);
  const [selectedExpiry, setSelectedExpiry] = useState<string>("");
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [chain, setChain] = useState<OptionChainResponse | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [candles, setCandles] = useState<ChartCandle[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [ledgerState, setLedgerState] = useState<import("../features/options/types").LedgerState | null>(null);
  const [selectedRow, setSelectedRow] = useState<OptionChainRow | null>(null);
  const [strikeSheetOpen, setStrikeSheetOpen] = useState(false);
  const [reloadNonce, setReloadNonce] = useState(0);
  const [storageReady, setStorageReady] = useState(false);
  const [loadingDashboard, setLoadingDashboard] = useState(true);
  const [loadingChain, setLoadingChain] = useState(true);
  const [loadingAnalytics, setLoadingAnalytics] = useState(true);
  const [loadingChart, setLoadingChart] = useState(true);
  const [errorDashboard, setErrorDashboard] = useState<string | null>(null);
  const [errorChain, setErrorChain] = useState<string | null>(null);
  const [errorAnalytics, setErrorAnalytics] = useState<string | null>(null);
  const [errorChart, setErrorChart] = useState<string | null>(null);
  const [upstoxStatus, setUpstoxStatus] = useState<UpstoxStatus | null>(null);
  const [chartOverlays, setChartOverlays] = useState({ ema: true, vwap: true, rsi: false, volume: true });
  const [chartSource, setChartSource] = useState<{ label: string; instrumentKey?: string }>({ label: "Index" });
  
  const [orderModalOpen, setOrderModalOpen] = useState(false);
  const [orderAction, setOrderAction] = useState<"BUY" | "SELL">("BUY");

  const [chartModalOpen, setChartModalOpen] = useState(false);
  const [chartModalTitle, setChartModalTitle] = useState("");
  const [chartModalInstrumentKey, setChartModalInstrumentKey] = useState<string | undefined>(undefined);

  const hasLoadedChain = useRef(false);
  const hasLoadedDashboard = useRef(false);
  const hasLoadedAnalytics = useRef(false);
  const hasLoadedChart = useRef(false);

  const symbol = selectedUnderlying?.symbol ?? "NIFTY";

  useEffect(() => {
    let active = true;
    optionsApi
      .getUpstoxStatus()
      .then((status) => {
        if (!active) return;
        setUpstoxStatus(status);
      })
      .catch(() => {
        if (!active) return;
        setUpstoxStatus({ connected: false, authMode: "none", message: "Unable to check Upstox status." });
      });

    optionsApi
      .search("NIFTY")
      .then((items) => {
        if (!active || items.length === 0) return;
        setSelectedUnderlying(items[0]);
      })
      .catch(() => {
        if (!active) return;
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setStorageReady(false);
    Promise.all([
      optionsPersistence.loadWatchlist(user?.id),
      optionsApi.getLedger(),
    ]).then(([watchItems, ledgerData]) => {
      if (!active) return;
      setWatchlist(watchItems);
      setLedgerState(ledgerData);
      setStorageReady(true);
    });
    return () => {
      active = false;
    };
  }, [user?.id]);

  useEffect(() => {
    if (!storageReady) return;
    optionsPersistence.saveWatchlist(watchlist, user?.id);
  }, [storageReady, watchlist, user?.id]);

  // Poll ledger + pending signals every 5s so new ideas & LTP updates auto-reflect
  useEffect(() => {
    let active = true;
    const pollLedger = () => {
      optionsApi.getLedger()
        .then((data) => { if (active) setLedgerState(data); })
        .catch(() => {});
    };
    const timer = window.setInterval(pollLedger, 3000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);


  useEffect(() => {
    hasLoadedChain.current = false;
    hasLoadedDashboard.current = false;
    hasLoadedAnalytics.current = false;
    hasLoadedChart.current = false;
    setLoadingDashboard(true);
    setLoadingChain(true);
    setLoadingAnalytics(true);
    setLoadingChart(true);
  }, [selectedUnderlying, selectedExpiry]);

  useEffect(() => {
    if (!selectedUnderlying) return;
    let active = true;

    if (!hasLoadedDashboard.current) {
      setLoadingDashboard(true);
    }
    setErrorDashboard(null);

    optionsApi
      .getDashboard(symbol, selectedExpiry || undefined)
      .then((data) => {
        if (!active) return;
        setDashboard(data);
        hasLoadedDashboard.current = true;
        if (!selectedExpiry || !data.expiries.includes(selectedExpiry)) {
          setSelectedExpiry(data.expiry);
        }
      })
      .catch((error: unknown) => {
        if (!active) return;
        setErrorDashboard(error instanceof Error ? error.message : "Unable to load options dashboard right now.");
      })
      .finally(() => {
        if (active) setLoadingDashboard(false);
      });

    return () => {
      active = false;
    };
  }, [selectedUnderlying, selectedExpiry, symbol]);

  useEffect(() => {
    if (!selectedUnderlying || !selectedExpiry) return;
    let active = true;

    const load = () => {
      if (!hasLoadedChain.current) setLoadingChain(true);
      if (!hasLoadedAnalytics.current) setLoadingAnalytics(true);
      if (!hasLoadedChart.current) setLoadingChart(true);
      setErrorChain(null);
      setErrorAnalytics(null);
      setErrorChart(null);

      optionsApi
        .getChain(symbol, selectedExpiry, filters.strikeCount)
        .then((data) => {
          if (!active) return;
          setChain(data);
          hasLoadedChain.current = true;
          setSelectedRow((current) =>
            current && data.rows.some((row) => row.strike === current.strike)
              ? data.rows.find((row) => row.strike === current.strike) ?? null
              : data.rows.find((row) => row.isAtm) ?? data.rows[0] ?? null
          );
        })
        .catch((error: unknown) => {
          if (!active) return;
          setErrorChain(error instanceof Error ? error.message : "Unable to load the option chain.");
        })
        .finally(() => {
          if (active) setLoadingChain(false);
        });

      optionsApi
        .getAnalytics(symbol, selectedExpiry)
        .then((data) => {
          if (!active) return;
          setAnalytics(data);
          hasLoadedAnalytics.current = true;
        })
        .catch((error: unknown) => {
          if (!active) return;
          setErrorAnalytics(error instanceof Error ? error.message : "Unable to derive analytics.");
        })
        .finally(() => {
          if (active) setLoadingAnalytics(false);
        });

      optionsApi
        .getChart(symbol, "5m", chartSource.instrumentKey)
        .then((data) => {
          if (!active) return;
          setCandles(data);
          hasLoadedChart.current = true;
        })
        .catch((error: unknown) => {
          if (!active) return;
          setErrorChart(error instanceof Error ? error.message : "Unable to load chart data.");
        })
        .finally(() => {
          if (active) setLoadingChart(false);
        });
    };

    load();
    if (!filters.autoRefresh) {
      return () => {
        active = false;
      };
    }

    const timer = window.setInterval(load, 5_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [filters.autoRefresh, filters.strikeCount, reloadNonce, selectedExpiry, selectedUnderlying, symbol, chartSource]);

  useEffect(() => {
    if (!selectedUnderlying || !selectedExpiry || !filters.autoRefresh) return;
    let active = true;

    const pollLtp = () => {
      optionsApi
        .getChainLtp(symbol, selectedExpiry)
        .then((ltpData) => {
          if (!active) return;
          setChain((prev) => {
            if (!prev) return prev;
            const mergedRows = mergeChainLtp(prev.rows, ltpData.rows);
            if (mergedRows === prev.rows) return prev;
            return { ...prev, rows: mergedRows };
          });
          setSelectedRow((current) => {
            if (!current) return current;
            const ltpHit = ltpData.rows.find((r) => r.strike === current.strike);
            if (!ltpHit) return current;
            if (current.call.ltp === ltpHit.callLtp && current.put.ltp === ltpHit.putLtp) return current;

            const callChange = ltpHit.callClosePrice ? ltpHit.callLtp - ltpHit.callClosePrice : current.call.change;
            const callChangePercent = ltpHit.callClosePrice ? ((ltpHit.callLtp - ltpHit.callClosePrice) / ltpHit.callClosePrice) * 100 : current.call.changePercent;
            const putChange = ltpHit.putClosePrice ? ltpHit.putLtp - ltpHit.putClosePrice : current.put.change;
            const putChangePercent = ltpHit.putClosePrice ? ((ltpHit.putLtp - ltpHit.putClosePrice) / ltpHit.putClosePrice) * 100 : current.put.changePercent;

            return {
              ...current,
              call: { ...current.call, ltp: ltpHit.callLtp, bid: ltpHit.callBid, ask: ltpHit.callAsk, change: callChange, changePercent: callChangePercent },
              put: { ...current.put, ltp: ltpHit.putLtp, bid: ltpHit.putBid, ask: ltpHit.putAsk, change: putChange, changePercent: putChangePercent },
            };
          });
        })
        .catch(() => {});

      optionsApi
        .getDashboard(symbol, selectedExpiry)
        .then((data) => {
          if (!active) return;
          setDashboard(data);
        })
        .catch(() => {});
    };

    const timer = window.setInterval(pollLtp, 500);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [filters.autoRefresh, selectedExpiry, selectedUnderlying, symbol]);

  const pinnedStrikeMarkers = useMemo(
    () =>
      watchlist
        .filter((item) => item.underlying === symbol && item.expiry === selectedExpiry && item.pinned)
        .map((item) => item.strike),
    [selectedExpiry, symbol, watchlist]
  );

  const [paperSide, setPaperSide] = useState<"CE" | "PE">("CE");

  const handleOpenChart = (contractSymbol: string, title: string) => {
    setChartModalTitle(title);
    setChartModalInstrumentKey(contractSymbol || undefined);
    setChartModalOpen(true);
  };

  const handleOpenStrike = (row: OptionChainRow) => {
    setSelectedRow(row);
    setStrikeSheetOpen(true);
  };

  let marketTrend = null;
  if (dashboard && analytics) {
    const pcr = parseFloat(analytics.analytics.pcr.value) || 0;
    const changePct = dashboard.quote.changePercent;
    
    if (changePct > 0.5 && pcr > 1.0) {
       marketTrend = { label: "Bullish", tone: "text-emerald-400", simple: "Strong upward momentum", tech: `Δ > 0.5% | PCR ${pcr.toFixed(2)} (Put Support)` };
    } else if (changePct < -0.5 && pcr < 0.8) {
       marketTrend = { label: "Bearish", tone: "text-red-400", simple: "Strong downward momentum", tech: `Δ < -0.5% | PCR ${pcr.toFixed(2)} (Call Resistance)` };
    } else if (changePct > 0.5 && pcr <= 1.0) {
       marketTrend = { label: "Mildly Bullish", tone: "text-emerald-400", simple: "Price is up, but facing resistance", tech: `Δ > 0.5% | PCR ${pcr.toFixed(2)} (Mixed)` };
    } else if (changePct < -0.5 && pcr >= 0.8) {
       marketTrend = { label: "Mildly Bearish", tone: "text-red-400", simple: "Price is down, but finding support", tech: `Δ < -0.5% | PCR ${pcr.toFixed(2)} (Mixed)` };
    } else {
       marketTrend = { label: "Choppy", tone: "text-amber-400", simple: "Sideways range-bound movement", tech: `|Δ| < 0.5% | PCR ${pcr.toFixed(2)}` };
    }
  }

  const summaryCards = dashboard
    ? [
        ["Spot Price", `₹${dashboard.quote.price.toFixed(2)}`, toneForChange(dashboard.quote.changePercent)],
        ["Day Change", `${dashboard.quote.changePercent.toFixed(2)}%`, toneForChange(dashboard.quote.changePercent)],
        dashboard.quote.volume > 0 
          ? ["Volume", dashboard.quote.volume.toLocaleString("en-IN"), "text-white"]
          : ["Day Range", `${dashboard.quote.dayLow.toFixed(2)} - ${dashboard.quote.dayHigh.toFixed(2)}`, "text-white"],
        ["ATM Strike", `${dashboard.atmStrike}`, "text-white"],
        ...(marketTrend ? [["Day Trend", marketTrend.label, marketTrend.tone, { simple: marketTrend.simple, tech: marketTrend.tech }]] : []),
      ]
    : [];

  // Handler: add to watchlist from chain
  const handleAddWatch = (row: OptionChainRow, side: "CE" | "PE") => {
    const leg = side === "CE" ? row.call : row.put;
    setWatchlist((current) => {
      // Toggle: if already watched, remove
      const existingIndex = current.findIndex((item) => item.contractSymbol === leg.contractSymbol);
      if (existingIndex >= 0) {
        return current.filter((_, i) => i !== existingIndex);
      }
      return [
        {
          id: crypto.randomUUID(),
          contractSymbol: leg.contractSymbol,
          underlying: symbol,
          expiry: selectedExpiry,
          strike: row.strike,
          side,
          pinned: false,
          createdAt: new Date().toISOString(),
        },
        ...current,
      ];
    });
  };

  // Handler: quick trade from chain (Buy/Sell buttons)
  const handleQuickTrade = (row: OptionChainRow, side: "CE" | "PE", action: "BUY" | "SELL") => {
    setSelectedRow(row);
    setPaperSide(side);
    setOrderAction(action);
    setOrderModalOpen(true);
  };

  const TAB_CLASS = "rounded-t-lg border border-transparent border-b-0 px-4 py-2.5 text-sm font-semibold text-white/40 data-[state=active]:border-white/10 data-[state=active]:bg-white/[0.03] data-[state=active]:text-white transition-all shadow-none";

  return (
    <div className="min-h-screen bg-[#050505] text-white font-sans selection:bg-emerald-500/30">
      <div className="pointer-events-none fixed inset-0 flex items-center justify-center">
        <div className="h-[600px] w-[800px] rounded-full bg-emerald-500/8 blur-[120px]" />
      </div>
      
      <div className="relative mx-auto max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8">
        
        {/* Header Section */}
        <div className="mb-6 flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">F&O Research</h1>
            <p className="mt-1 max-w-xl text-sm text-white/50">
              Options chain, analytics, charting, and virtual paper trading.
            </p>
          </div>
          <div className="w-full max-w-md">
            <OptionsSearch
              value={symbol}
              onSelect={(item) => {
                setSelectedUnderlying(item);
                setSelectedExpiry("");
                setSelectedRow(null);
                setStrikeSheetOpen(false);
              }}
            />
          </div>
        </div>

        {/* Dashboard Overview */}
        <div className="mb-6 grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {loadingDashboard
            ? Array.from({ length: 5 }, (_, index) => (
                <div key={index} className="h-[72px] rounded-xl bg-white/[0.03] border border-white/10 animate-pulse" />
              ))
            : summaryCards.map(([label, value, tone, subtext]: any) => (
                <div key={label} className="flex flex-col justify-center rounded-xl bg-white/[0.03] border border-white/10 p-4 relative overflow-hidden group hover:border-white/20 transition-colors">
                  <div className="absolute inset-0 bg-gradient-to-br from-white/[0.04] to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
                  <div className="text-[10px] font-bold text-white/35 uppercase tracking-[0.15em]">{label}</div>
                  <div className={`mt-1 text-lg font-bold ${tone}`}>{value}</div>
                  {subtext && typeof subtext === "string" && <div className="mt-1 text-[10px] font-medium text-white/40">{subtext}</div>}
                  {subtext && typeof subtext === "object" && (
                    <div className="mt-1 flex flex-col gap-0.5">
                      <span className="text-[10px] font-medium text-white/60">{subtext.simple}</span>
                      <span className="text-[9px] font-mono text-white/30">{subtext.tech}</span>
                    </div>
                  )}
                </div>
              ))}
        </div>

        {errorDashboard && (
          <div className="mb-6 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            <div>{errorDashboard}</div>
            {!upstoxStatus?.connected && errorDashboard.includes("Upstox authentication required") && (
              <a
                href="http://localhost:4000/auth/upstox"
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-block font-semibold text-red-300 hover:text-red-200"
              >
                Connect Upstox →
              </a>
            )}
          </div>
        )}

        {/* Expiry Selector and Controls */}
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-3 rounded-lg bg-white/[0.03] border border-white/10 px-4 py-2">
              <span className="text-xs font-bold text-white/35 uppercase tracking-[0.15em]">Expiry</span>
              <select
                value={selectedExpiry}
                onChange={(event) => setSelectedExpiry(event.target.value)}
                className="bg-transparent text-sm font-semibold text-white outline-none cursor-pointer"
              >
                {(dashboard?.expiries ?? []).map((expiry) => (
                  <option key={expiry} value={expiry} className="bg-[#0a0a0a] text-white">
                    {expiry}
                  </option>
                ))}
              </select>
            </label>
            <button
              onClick={() => setReloadNonce((value) => value + 1)}
              className="flex items-center gap-2 rounded-lg bg-white/[0.03] border border-white/10 px-3 py-2 text-xs font-medium text-white/40 hover:text-white transition-colors"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Refresh
            </button>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-[10px] font-medium text-white/30 tracking-wider">
              {chain?.meta.source === "generated-research"
                ? "Simulated Data"
                : chain?.meta.source === "upstox"
                  ? "Live Upstox"
                  : ""}
            </div>
            {ledgerState && ledgerState.trades.filter((p) => p.status === "OPEN").length > 0 && (
              <div className="rounded-full bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 text-[10px] font-bold text-emerald-400 tracking-wider">
                {ledgerState.trades.filter((p) => p.status === "OPEN").length} Open Position{ledgerState.trades.filter((p) => p.status === "OPEN").length > 1 ? "s" : ""}
              </div>
            )}
          </div>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="flex w-full overflow-x-auto justify-start gap-1 border-b border-white/10 bg-transparent p-0 pb-px">
            <TabsTrigger value="chain" className={TAB_CLASS}>Option Chain</TabsTrigger>
            <TabsTrigger value="ledger" className={TAB_CLASS}>Positions & Ledger</TabsTrigger>
            <TabsTrigger value="chart" className={TAB_CLASS}>Chart</TabsTrigger>
            <TabsTrigger value="watchlist" className={TAB_CLASS}>
              Watchlist
              {watchlist.length > 0 && (
                <span className="ml-1.5 inline-flex h-4 w-4 items-center justify-center rounded-full bg-amber-500/20 text-[9px] font-bold text-amber-400">
                  {watchlist.length}
                </span>
              )}
            </TabsTrigger>
          </TabsList>

          <div className="mt-5">
            <TabsContent value="chain" className="m-0">
              <OptionsChainTable
                key={`${symbol}-${selectedExpiry}`}
                rows={chain?.rows ?? []}
                filters={filters}
                onFiltersChange={setFilters}
                loading={loadingChain}
                error={errorChain}
                watchlist={watchlist}
                onOpenStrike={handleOpenStrike}
                onAddWatch={handleAddWatch}
                onTrade={handleQuickTrade}
                onDetails={handleOpenStrike}
                onOpenChart={handleOpenChart}
              />
            </TabsContent>

            <TabsContent value="ledger" className="m-0">
              <OptionsPositionsPanel
                ledgerState={ledgerState}
                rows={chain?.rows ?? []}
                onClose={(id, exit) => {
                  optionsApi.closeTrade(id, exit)
                    .then(setLedgerState)
                    .catch(e => alert(e.message));
                }}
              />
            </TabsContent>

            <TabsContent value="chart" className="m-0 space-y-4">
              {/* Chart source selector */}
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                <div className="mb-2 text-[10px] uppercase tracking-[0.2em] text-white/35">Chart Source</div>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => { setChartSource({ label: "Index" }); hasLoadedChart.current = false; setLoadingChart(true); }}
                    className={`rounded-full px-4 py-1.5 text-xs font-bold tracking-wide transition-colors ${
                      !chartSource.instrumentKey ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shadow-[0_0_12px_rgba(16,185,129,0.2)]" : "bg-white/[0.03] text-white/40 hover:text-white border border-white/10"
                    }`}
                  >
                    {symbol} Index
                  </button>
                  {(chain?.rows ?? []).filter((r) => r.isAtm || Math.abs(r.strike - (chain?.atmStrike ?? 0)) <= (chain?.strikeStep ?? 50) * 3).map((row) => (
                    [
                      { label: `${row.strike} CE`, key: row.call.contractSymbol },
                      { label: `${row.strike} PE`, key: row.put.contractSymbol },
                    ].map((opt) => (
                      <button
                        key={opt.key}
                        onClick={() => { setChartSource({ label: opt.label, instrumentKey: opt.key }); hasLoadedChart.current = false; setLoadingChart(true); }}
                        className={`rounded-full px-3 py-1.5 text-xs font-bold tracking-wide transition-colors ${
                          chartSource.instrumentKey === opt.key ? "bg-sky-500/20 text-sky-400 border border-sky-500/30 shadow-[0_0_12px_rgba(56,189,248,0.2)]" : "bg-white/[0.03] text-white/40 hover:text-white border border-white/10"
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))
                  ))}
                </div>
              </div>
              {/* Overlay toggles */}
              <div className="flex flex-wrap gap-2">
                {Object.entries(chartOverlays).map(([key, enabled]) => (
                  <button
                    key={key}
                    onClick={() => setChartOverlays((current) => ({ ...current, [key]: !enabled }))}
                    className={`rounded-full px-4 py-1.5 text-xs font-bold tracking-wide transition-colors ${
                      enabled ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shadow-[0_0_12px_rgba(16,185,129,0.2)]" : "bg-white/[0.03] text-white/40 hover:text-white border border-white/10"
                    }`}
                  >
                    {key.toUpperCase()}
                  </button>
                ))}
              </div>
              {loadingChart ? (
                <div className="rounded-xl bg-white/[0.03] border border-white/10 p-6 text-sm text-white/40">Loading chart…</div>
              ) : errorChart ? (
                <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-sm text-red-200">{errorChart}</div>
              ) : candles.length === 0 ? (
                <div className="rounded-xl bg-white/[0.03] border border-white/10 p-8 text-center text-sm text-white/40">
                  No chart data available for {chartSource.label}.
                </div>
              ) : (
                <OptionsChartPanel
                  candles={candles}
                  atmStrike={chain?.atmStrike ?? dashboard?.atmStrike ?? 0}
                  strikeMarkers={pinnedStrikeMarkers}
                  overlays={chartOverlays}
                  chartLabel={chartSource.instrumentKey ? `${symbol} ${chartSource.label}` : `${symbol} Index`}
                />
              )}
            </TabsContent>

            <TabsContent value="watchlist" className="m-0">
              <OptionsWatchlistPanel
                items={watchlist}
                onTogglePin={(id) => {
                  setWatchlist((current) =>
                    current.map((item) => (item.id === id ? { ...item, pinned: !item.pinned } : item))
                  );
                }}
                onRemove={(id) => setWatchlist((current) => current.filter((item) => item.id !== id))}
              />
            </TabsContent>
          </div>
        </Tabs>
      </div>

      <StrikeDetailSheet
        row={selectedRow}
        expiry={selectedExpiry}
        open={strikeSheetOpen}
        onOpenChange={setStrikeSheetOpen}
      />

      <OptionsOrderModal
        isOpen={orderModalOpen}
        onClose={() => setOrderModalOpen(false)}
        row={selectedRow}
        side={paperSide}
        action={orderAction}
        underlying={symbol}
        expiry={selectedExpiry}
        onSubmit={(position) => {
          optionsApi.openTrade({ ...position, entryPrice: position.entry })
            .then(setLedgerState)
            .catch(e => alert(e.message));
        }}
      />

      <OptionChartModal
        isOpen={chartModalOpen}
        onClose={() => setChartModalOpen(false)}
        title={chartModalTitle}
        symbol={symbol}
        instrumentKey={chartModalInstrumentKey}
      />
    </div>
  );
}
