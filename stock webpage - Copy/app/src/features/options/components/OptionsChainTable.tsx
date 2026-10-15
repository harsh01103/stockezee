import { Eye, Search, Star } from "lucide-react";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import type { ChainFilters, OptionChainRow, OptionLeg, WatchlistItem } from "../types";

function metricTone(value: number) {
  if (value > 0) return "text-emerald-400";
  if (value < 0) return "text-red-400";
  return "text-white/40";
}

const TICK_STYLES = `
@keyframes tickUp {
  0% { color: #34d399; text-shadow: 0 0 12px rgba(52,211,153,0.8); background-color: rgba(52,211,153,0.15); }
  100% { text-shadow: none; background-color: transparent; }
}
@keyframes tickDown {
  0% { color: #f87171; text-shadow: 0 0 12px rgba(248,113,113,0.8); background-color: rgba(248,113,113,0.15); }
  100% { text-shadow: none; background-color: transparent; }
}
.tick-up { animation: tickUp 600ms ease-out; }
.tick-down { animation: tickDown 600ms ease-out; }
.ltp-value { transition: color 150ms ease; padding: 2px 4px; border-radius: 4px; }
`;

function PriceCell({ value, className = "" }: { value: number; className?: string }) {
  const prevRef = useRef(value);
  const [tickClass, setTickClass] = useState("");
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const prev = prevRef.current;
    if (prev !== value && prev !== 0) {
      setTickClass(value > prev ? "tick-up" : "tick-down");
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setTickClass(""), 600);
    }
    prevRef.current = value;
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [value]);

  return (
    <span className={`ltp-value ${tickClass} ${className}`}>
      ₹{value.toFixed(2)}
    </span>
  );
}

function formatCompact(value: number): string {
  if (value >= 10_000_000) return (value / 10_000_000).toFixed(1) + "Cr";
  if (value >= 100_000) return (value / 100_000).toFixed(1) + "L";
  if (value >= 1_000) return (value / 1_000).toFixed(1) + "K";
  return value.toString();
}

/** Single leg cell — shows LTP, change%, OI, Vol and action buttons */
const LegCell = memo(function LegCell({
  leg,
  side,
  isWatched,
  onWatch,
  onTrade,
  onDetails,
  onOpenChart,
}: {
  leg: OptionLeg;
  side: "CE" | "PE";
  isWatched: boolean;
  onWatch: () => void;
  onTrade: (action: "BUY" | "SELL") => void;
  onDetails: () => void;
  onOpenChart: () => void;
}) {
  return (
    <div 
      className="group relative grid grid-cols-[1fr_70px_70px] items-center gap-0 px-2 py-2.5 hover:bg-white/[0.03] transition-colors cursor-pointer"
      onClick={onOpenChart}
    >
      {/* Price + Change */}
      <div className="flex items-center gap-2">
        <div className="min-w-0">
          <div className="text-sm font-bold text-white tabular-nums">
            <PriceCell value={leg.ltp} />
          </div>
          <div className={`text-[11px] font-semibold tabular-nums ${metricTone(leg.changePercent)}`}>
            {leg.changePercent > 0 ? "+" : ""}{leg.changePercent.toFixed(2)}%
          </div>
        </div>
      </div>

      {/* OI */}
      <div className="text-right">
        <div className="text-xs font-medium text-white/60 tabular-nums">{formatCompact(leg.oi)}</div>
      </div>

      {/* Volume */}
      <div className="text-right">
        <div className="text-xs font-medium text-white/60 tabular-nums">{formatCompact(leg.volume)}</div>
      </div>

      {/* Hover overlay with action buttons */}
      <div 
        className="absolute inset-0 flex items-center justify-end gap-1 px-2 opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-l from-[#0c1420] via-[#0c1420]/95 to-transparent pointer-events-none group-hover:pointer-events-auto"
        onClick={onOpenChart}
      >
        <button
          onClick={(e) => { e.stopPropagation(); onTrade("BUY"); }}
          className="px-2.5 py-1 rounded-md bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] font-bold uppercase tracking-wider hover:bg-emerald-500/30 transition-colors"
          title={`Buy ${side}`}
        >
          B
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onTrade("SELL"); }}
          className="px-2.5 py-1 rounded-md bg-red-500/20 text-red-400 border border-red-500/30 text-[10px] font-bold uppercase tracking-wider hover:bg-red-500/30 transition-colors"
          title={`Sell ${side}`}
        >
          S
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onWatch(); }}
          className={`p-1 rounded-md transition-colors ${isWatched ? "text-amber-400" : "text-white/40 hover:text-amber-400"}`}
          title={isWatched ? "Remove from watchlist" : "Add to watchlist"}
        >
          <Star className={`h-3.5 w-3.5 ${isWatched ? "fill-current" : ""}`} />
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onDetails(); }}
          className="p-1 rounded-md text-white/40 hover:text-white transition-colors"
          title="View details"
        >
          <Eye className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
});

const ChainRow = memo(function ChainRow({
  row,
  watchlist,
  onOpenStrike,
  onAddWatch,
  onTrade,
  onDetails,
  onOpenChart,
}: {
  row: OptionChainRow;
  watchlist: WatchlistItem[];
  onOpenStrike: () => void;
  onAddWatch: (leg: OptionLeg, side: "CE" | "PE") => void;
  onTrade: (row: OptionChainRow, side: "CE" | "PE", action: "BUY" | "SELL") => void;
  onDetails: (row: OptionChainRow) => void;
  onOpenChart: (contractSymbol: string, title: string) => void;
}) {
  const ceWatched = watchlist.some((w) => w.contractSymbol === row.call.contractSymbol);
  const peWatched = watchlist.some((w) => w.contractSymbol === row.put.contractSymbol);

  return (
    <div className={`grid grid-cols-[1fr_auto_1fr] border-b border-white/[0.04] items-stretch ${row.isAtm ? "bg-amber-500/[0.04] border-l-2 border-l-amber-400/50" : ""}`}>
      {/* Call Side */}
      <div className={`${row.call.moneyness === "ITM" ? "bg-emerald-500/[0.03]" : ""}`}>
        <LegCell
          leg={row.call}
          side="CE"
          isWatched={ceWatched}
          onWatch={() => onAddWatch(row.call, "CE")}
          onTrade={(action) => onTrade(row, "CE", action)}
          onDetails={() => onDetails(row)}
          onOpenChart={() => onOpenChart(row.call.contractSymbol, `${row.strike} CE`)}
        />
      </div>

      {/* Center Strike */}
      <div 
        className="w-[90px] flex flex-col items-center justify-center px-2 border-x border-white/[0.06] bg-white/[0.015] cursor-pointer hover:bg-white/[0.05] transition-colors"
        onClick={() => onOpenChart("", "Underlying Index")}
      >
        {row.isAtm && <div className="text-[8px] font-bold text-amber-400 tracking-[0.3em] uppercase mb-0.5">ATM</div>}
        <button
          onClick={(e) => { e.stopPropagation(); onOpenStrike(); }}
          className="text-sm font-bold text-white/80 hover:text-white transition-colors tabular-nums"
        >
          {row.strike}
        </button>
      </div>

      {/* Put Side */}
      <div className={`${row.put.moneyness === "ITM" ? "bg-red-500/[0.03]" : ""}`}>
        <LegCell
          leg={row.put}
          side="PE"
          isWatched={peWatched}
          onWatch={() => onAddWatch(row.put, "PE")}
          onTrade={(action) => onTrade(row, "PE", action)}
          onDetails={() => onDetails(row)}
          onOpenChart={() => onOpenChart(row.put.contractSymbol, `${row.strike} PE`)}
        />
      </div>
    </div>
  );
});

export function OptionsChainTable({
  rows,
  filters,
  onFiltersChange,
  loading,
  error,
  watchlist,
  onOpenStrike,
  onAddWatch,
  onTrade,
  onDetails,
  onOpenChart,
}: {
  rows: OptionChainRow[];
  filters: ChainFilters;
  onFiltersChange: (filters: ChainFilters) => void;
  loading: boolean;
  error: string | null;
  watchlist: WatchlistItem[];
  onAddWatch: (row: OptionChainRow, side: "CE" | "PE") => void;
  onOpenStrike: (row: OptionChainRow) => void;
  onTrade: (row: OptionChainRow, side: "CE" | "PE", action: "BUY" | "SELL") => void;
  onDetails: (row: OptionChainRow) => void;
  onOpenChart: (contractSymbol: string, title: string) => void;
}) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);

  const styleInjected = useRef(false);
  useEffect(() => {
    if (styleInjected.current) return;
    styleInjected.current = true;
    const style = document.createElement("style");
    style.textContent = TICK_STYLES;
    document.head.appendChild(style);
  }, []);

  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      const liquidity = Math.max(row.call.volume + row.call.oi, row.put.volume + row.put.oi);
      const matchesLiquidity = liquidity >= filters.minLiquidity;
      const matchesStrike = row.strike.toString().includes(filters.strikeQuery.trim());
      return matchesLiquidity && matchesStrike;
    });
  }, [filters.minLiquidity, filters.strikeQuery, rows]);

  // Scroll ATM into view on first load
  const hasScrolledToAtm = useRef(false);
  useEffect(() => {
    if (hasScrolledToAtm.current || !viewportRef.current || filteredRows.length === 0) return;
    const atmIndex = filteredRows.findIndex((r) => r.isAtm);
    if (atmIndex >= 0) {
      const targetScroll = Math.max(0, atmIndex * 58 - 200);
      viewportRef.current.scrollTop = targetScroll;
      hasScrolledToAtm.current = true;
    }
  }, [filteredRows]);

  const rowHeight = 58;
  const viewportHeight = 600;
  const start = Math.max(0, Math.floor(scrollTop / rowHeight) - 4);
  const visibleCount = Math.ceil(viewportHeight / rowHeight) + 8;
  const visibleRows = filteredRows.slice(start, start + visibleCount);
  const topPad = start * rowHeight;
  const bottomPad = Math.max(0, (filteredRows.length - start - visibleRows.length) * rowHeight);

  return (
    <div className="space-y-3">
      {/* Filters bar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-2 rounded-lg bg-white/[0.03] border border-white/10 px-3 py-1.5 text-sm">
          <Search className="h-3.5 w-3.5 text-white/40" />
          <input
            value={filters.strikeQuery}
            onChange={(event) => onFiltersChange({ ...filters, strikeQuery: event.target.value })}
            placeholder="Strike"
            className="w-24 bg-transparent text-white text-xs outline-none placeholder:text-white/25"
          />
        </div>

        <select
          value={filters.strikeCount}
          onChange={(event) => onFiltersChange({ ...filters, strikeCount: Number(event.target.value) })}
          className="rounded-lg bg-white/[0.03] border border-white/10 px-3 py-1.5 text-xs font-medium text-white outline-none cursor-pointer"
        >
          {[21, 31, 41, 51].map((count) => (
            <option key={count} value={count} className="bg-[#0a0a0a]">{count} Strikes</option>
          ))}
        </select>

        <button
          onClick={() => onFiltersChange({ ...filters, autoRefresh: !filters.autoRefresh })}
          className={`rounded-lg px-3 py-1.5 text-xs font-bold tracking-wide transition-colors border ${
            filters.autoRefresh
              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
              : "bg-white/[0.03] text-white/40 border-white/10 hover:text-white"
          }`}
        >
          {filters.autoRefresh ? "● Live" : "○ Paused"}
        </button>

        <div className="ml-auto text-[10px] text-white/30 font-medium tracking-wider">
          Hover any row for B/S & ★
        </div>
      </div>

      {/* Chain table */}
      <div className="rounded-2xl border border-white/10 bg-white/[0.02] overflow-hidden shadow-xl">
        {loading ? (
          <div className="p-12 text-center text-sm font-medium text-white/40">Loading Option Chain…</div>
        ) : error ? (
          <div className="p-12 text-center text-sm font-medium text-red-400">{error}</div>
        ) : filteredRows.length === 0 ? (
          <div className="p-12 text-center text-sm font-medium text-white/40">No strikes found.</div>
        ) : (
          <div className="flex flex-col">
            {/* Column headers */}
            <div className="grid grid-cols-[1fr_auto_1fr] bg-white/[0.03] border-b border-white/10 sticky top-0 z-20">
              {/* Call header */}
              <div className="grid grid-cols-[1fr_70px_70px] px-2 py-2">
                <div className="text-[10px] font-bold text-emerald-400/70 tracking-[0.15em] uppercase">Calls LTP</div>
                <div className="text-[10px] font-bold text-white/30 tracking-[0.15em] uppercase text-right">OI</div>
                <div className="text-[10px] font-bold text-white/30 tracking-[0.15em] uppercase text-right">Vol</div>
              </div>
              {/* Strike header */}
              <div className="w-[90px] flex items-center justify-center px-2 border-x border-white/[0.06]">
                <div className="text-[10px] font-bold text-white/30 tracking-[0.15em] uppercase">Strike</div>
              </div>
              {/* Put header */}
              <div className="grid grid-cols-[1fr_70px_70px] px-2 py-2">
                <div className="text-[10px] font-bold text-red-400/70 tracking-[0.15em] uppercase">Puts LTP</div>
                <div className="text-[10px] font-bold text-white/30 tracking-[0.15em] uppercase text-right">OI</div>
                <div className="text-[10px] font-bold text-white/30 tracking-[0.15em] uppercase text-right">Vol</div>
              </div>
            </div>

            {/* Virtualized rows */}
            <div
              ref={viewportRef}
              onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
              className="overflow-auto"
              style={{ maxHeight: viewportHeight }}
            >
              <div style={{ paddingTop: topPad, paddingBottom: bottomPad }}>
                {visibleRows.map((row) => (
                  <ChainRow
                    key={row.strike}
                    row={row}
                    watchlist={watchlist}
                    onOpenStrike={() => onOpenStrike(row)}
                    onAddWatch={onAddWatch}
                    onTrade={onTrade}
                    onDetails={onDetails}
                    onOpenChart={onOpenChart}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
