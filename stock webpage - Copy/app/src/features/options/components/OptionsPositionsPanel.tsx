import { useState } from "react";
import type { OptionChainRow, LedgerState } from "../types";

export function OptionsPositionsPanel({
  ledgerState,
  rows,
  onClose,
}: {
  ledgerState: LedgerState | null;
  rows: OptionChainRow[];
  onClose: (id: string, exit: number) => void;
}) {
  const [tab, setTab] = useState<"OPEN" | "CLOSED" | "QUEUED">("OPEN");

  if (!ledgerState) return null;

  const openTrades = ledgerState.trades.filter(t => t.status === "OPEN");
  const closedTrades = ledgerState.trades.filter(t => t.status === "CLOSED");
  const pendingSignals = ledgerState.pendingSignals || [];

  return (
    <div className="bg-[#0a0c10]/50 border border-white/10 rounded-xl overflow-hidden backdrop-blur-sm">
      <div className="w-full">
        
        {/* Ledger Header Stats */}
        <div className="flex flex-wrap items-center justify-between py-3 border-b border-white/5 gap-4">
          <div className="flex items-center gap-4 px-4">
            <button
              onClick={() => setTab("OPEN")}
              className={`text-sm font-bold uppercase tracking-widest px-3 py-1 rounded transition-colors ${tab === "OPEN" ? "bg-white/10 text-white" : "text-white/40 hover:text-white"}`}
            >
              Active ({openTrades.length})
            </button>
            <button
              onClick={() => setTab("CLOSED")}
              className={`text-sm font-bold uppercase tracking-widest px-3 py-1 rounded transition-colors ${tab === "CLOSED" ? "bg-white/10 text-white" : "text-white/40 hover:text-white"}`}
            >
              Ledger ({closedTrades.length})
            </button>
            <button
              onClick={() => setTab("QUEUED")}
              className={`text-sm font-bold uppercase tracking-widest px-3 py-1 rounded transition-colors ${tab === "QUEUED" ? "bg-white/10 text-white" : "text-white/40 hover:text-white"}`}
            >
              Queued ({pendingSignals.length})
            </button>
          </div>
          
          <div className="flex items-center gap-6 text-right px-4">
            <div>
              <div className="text-[10px] font-semibold text-white/40 uppercase tracking-widest">Balance</div>
              <div className="text-sm font-mono font-bold text-white">₹{ledgerState.balance.toFixed(2)}</div>
            </div>
            <div>
              <div className="text-[10px] font-semibold text-white/40 uppercase tracking-widest">Total P&L</div>
              <div className={`text-sm font-mono font-bold ${ledgerState.totalPnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {ledgerState.totalPnl > 0 ? "+" : ""}₹{ledgerState.totalPnl.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-semibold text-white/40 uppercase tracking-widest">Avg Profit / Trade</div>
              <div className={`text-sm font-mono font-bold ${ledgerState.avgProfit >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {ledgerState.avgProfit > 0 ? "+" : ""}₹{ledgerState.avgProfit.toFixed(2)}
              </div>
            </div>
            <div className="hidden sm:block">
              <div className="text-[10px] font-semibold text-white/40 uppercase tracking-widest">Prev Trade</div>
              <div className={`text-sm font-mono font-bold ${ledgerState.latestTradePnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {ledgerState.latestTradePnl > 0 ? "+" : ""}₹{ledgerState.latestTradePnl.toFixed(2)}
              </div>
            </div>
          </div>
        </div>

        <div className="max-h-[60vh] overflow-y-auto custom-scrollbar px-4 sm:px-6 lg:px-8">
          <div className="divide-y divide-white/5">
            {tab === "QUEUED" && pendingSignals.length === 0 && (
              <div className="py-8 text-center text-sm text-white/40">No queued signals. Waiting for incoming trade ideas...</div>
            )}
            {tab === "QUEUED" && pendingSignals.map((signal) => {
              const liveLtp = signal.currentLtp ?? null;
              const ltpColor = liveLtp !== null
                ? liveLtp >= signal.limitPrice ? "text-emerald-400" : "text-amber-400"
                : "text-white/40";
              
              return (
                <div key={signal.id} className="py-3 flex items-center justify-between hover:bg-white/[0.02] transition-colors">
                  <div className="flex items-center gap-4">
                    <div className="px-2 py-1 rounded text-xs font-bold border bg-blue-500/10 text-blue-400 border-blue-500/20">
                      QUEUED
                    </div>
                    <div>
                      <div className="text-sm font-bold text-white">{signal.contractSymbol}</div>
                      <div className="text-xs text-white/50">Dir: {signal.direction}{signal.strategy ? ` • ${signal.strategy}` : ''}{signal.confidence ? ` • ${signal.confidence}%` : ''}</div>
                    </div>
                  </div>
                  
                  <div className="flex flex-wrap items-center gap-4 sm:gap-6 justify-end">
                    <div className="text-right">
                      <div className="text-[10px] font-semibold text-white/40 uppercase tracking-widest">Entry Limit</div>
                      <div className="text-sm font-mono text-white">₹{signal.limitPrice.toFixed(2)}</div>
                    </div>
                    <div className="text-right hidden sm:block">
                      <div className="text-[10px] font-semibold text-red-400/60 uppercase tracking-widest">SL</div>
                      <div className="text-sm font-mono text-red-400/80">₹{signal.stopLoss?.toFixed(2) ?? '—'}</div>
                    </div>
                    <div className="text-right hidden sm:block">
                      <div className="text-[10px] font-semibold text-emerald-400/60 uppercase tracking-widest">Target</div>
                      <div className="text-sm font-mono text-emerald-400/80">₹{signal.target1?.toFixed(2) ?? '—'}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] font-semibold text-white/40 uppercase tracking-widest flex items-center justify-end gap-1">
                        {liveLtp !== null && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />}
                        Current LTP
                      </div>
                      <div className={`text-sm font-mono font-bold ${ltpColor}`}>{liveLtp !== null ? `₹${liveLtp.toFixed(2)}` : "Waiting..."}</div>
                    </div>
                  </div>
                </div>
              );
            })}

            {tab === "OPEN" && openTrades.length === 0 && (
              <div className="py-8 text-center text-sm text-white/40">No open positions.</div>
            )}
            {tab === "OPEN" && openTrades.map((pos) => {
              // Use backend-provided LTP (from AutoTrader, independent of viewed chain)
              // Fall back to chain row lookup, then entry price
              const chainRow = rows.find(r => r.strike === pos.strike);
              const chainLtp = chainRow ? (pos.side === "CE" ? chainRow.call.ltp : chainRow.put.ltp) : null;
              const liveLtp = pos.currentLtp ?? chainLtp ?? pos.entryPrice;
              const hasLiveFeed = pos.currentLtp != null || chainLtp != null;
              
              const longPosition = pos.action === "BUY";
              const pnl = longPosition ? (liveLtp - pos.entryPrice) * pos.qty : (pos.entryPrice - liveLtp) * pos.qty;
              const pnlTone = pnl > 0 ? "text-emerald-400" : pnl < 0 ? "text-red-400" : "text-white/60";
              
              return (
                <div key={pos.id} className="py-3 flex items-center justify-between hover:bg-white/[0.02] transition-colors">
                  <div className="flex items-center gap-4">
                    <div className={`px-2 py-1 rounded text-xs font-bold border ${pos.action === "BUY" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"}`}>
                      {pos.action}
                    </div>
                    <div>
                      <div className="text-sm font-bold text-white">{pos.contractSymbol}</div>
                      <div className="text-xs text-white/50">{pos.notes || "No notes"}</div>
                    </div>
                  </div>
                  
                  <div className="flex flex-wrap items-center gap-4 sm:gap-8 justify-end">
                    <div className="text-right">
                      <div className="text-[10px] font-semibold text-white/40 uppercase tracking-widest">Entry</div>
                      <div className="text-sm font-mono text-white">₹{pos.entryPrice.toFixed(2)}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] font-semibold text-white/40 uppercase tracking-widest flex items-center justify-end gap-1">
                        {hasLiveFeed && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />}
                        LTP
                      </div>
                      <div className={`text-sm font-mono font-bold ${hasLiveFeed ? (liveLtp >= pos.entryPrice ? "text-emerald-400" : "text-red-400") : "text-white"}`}>₹{liveLtp.toFixed(2)}</div>
                    </div>
                    <div className="text-right hidden sm:block">
                      <div className="text-[10px] font-semibold text-white/40 uppercase tracking-widest">Qty</div>
                      <div className="text-sm font-mono text-white">{pos.qty}</div>
                    </div>
                    <div className="text-right w-24">
                      <div className="text-[10px] font-semibold text-white/40 uppercase tracking-widest">Live P&L</div>
                      <div className={`text-sm font-bold font-mono ${pnlTone}`}>
                        {pnl > 0 ? "+" : ""}₹{pnl.toFixed(2)}
                      </div>
                    </div>
                    
                    <button
                      onClick={() => onClose(pos.id, liveLtp)}
                      className="px-4 py-1.5 rounded bg-red-500/10 text-red-400 border border-red-500/20 text-xs font-bold uppercase tracking-wider hover:bg-red-500/20 transition-colors"
                    >
                      Exit
                    </button>
                  </div>
                </div>
              );
            })}

            {(() => {
              if (tab !== "CLOSED") return null;

              const filteredTrades = closedTrades.filter(pos => (pos.netPnl ?? pos.pnl ?? 0) !== 0);
              
              return (
                <>
                  {filteredTrades.length === 0 ? (
                    <div className="py-8 text-center text-sm text-white/40">No closed trades in ledger.</div>
                  ) : filteredTrades.map((pos) => {
              const grossPnl = pos.grossPnl ?? pos.pnl ?? 0;
              const netPnl = pos.netPnl ?? pos.pnl ?? 0;
              const entryCharges = pos.entryCharges?.total ?? 0;
              const exitCharges = pos.exitCharges?.total ?? 0;
              const totalCharges = entryCharges + exitCharges;
              const endingBalance = pos.endingBalance;

              const pnlTone = netPnl > 0 ? "text-emerald-400" : netPnl < 0 ? "text-red-400" : "text-white/60";
              
              const isLoss = netPnl < 0;
              let lossReason = "";
              if (isLoss) {
                if (grossPnl > 0) {
                  lossReason = "Taxes Only";
                } else {
                  lossReason = "Market Loss";
                }
              }
              
              return (
                <div key={pos.id} className="py-4 flex items-center justify-between hover:bg-white/[0.02] transition-colors border-b border-white/5 last:border-0 opacity-90">
                  <div className="flex items-center gap-4">
                    <div className={`px-2 py-1 rounded text-xs font-bold border ${pos.action === "BUY" ? "bg-emerald-500/5 text-emerald-400/50 border-emerald-500/10" : "bg-red-500/5 text-red-400/50 border-red-500/10"}`}>
                      {pos.action}
                    </div>
                    <div>
                      <div className="text-sm font-bold text-white flex items-center gap-2">
                        {pos.contractSymbol}
                        {isLoss && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold tracking-wider uppercase bg-red-500/10 text-red-400 border border-red-500/20">
                            {lossReason}
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-white/40 mt-0.5">{new Date(pos.exitTimestamp || pos.timestamp).toLocaleString()}</div>
                    </div>
                  </div>
                  
                  <div className="flex flex-wrap items-center gap-4 sm:gap-6 justify-end">
                    <div className="text-right">
                      <div className="text-[10px] font-semibold text-white/40 uppercase tracking-widest">Entry / Exit</div>
                      <div className="text-sm font-mono text-white/60">₹{pos.entryPrice.toFixed(2)} / ₹{pos.exitPrice?.toFixed(2)}</div>
                    </div>
                    <div className="text-right hidden sm:block">
                      <div className="text-[10px] font-semibold text-white/40 uppercase tracking-widest">Gross P&L</div>
                      <div className="text-sm font-mono text-white/60">
                        {grossPnl > 0 ? "+" : ""}₹{grossPnl.toFixed(2)}
                      </div>
                    </div>
                    <div className="text-right hidden sm:block">
                      <div className="text-[10px] font-semibold text-white/40 uppercase tracking-widest">Charges</div>
                      <div className="text-sm font-mono text-red-400/50">-₹{totalCharges.toFixed(2)}</div>
                    </div>
                    <div className="text-right w-24">
                      <div className="text-[10px] font-semibold text-white/40 uppercase tracking-widest">Net P&L</div>
                      <div className={`text-sm font-bold font-mono ${pnlTone}`}>
                        {netPnl > 0 ? "+" : ""}₹{netPnl.toFixed(2)}
                      </div>
                    </div>
                    {endingBalance !== null && endingBalance !== undefined && (
                      <div className="text-right hidden lg:block w-28">
                        <div className="text-[10px] font-semibold text-white/40 uppercase tracking-widest">Ending Bal</div>
                        <div className="text-sm font-mono text-white/60">₹{endingBalance.toFixed(2)}</div>
                      </div>
                    )}
                  </div>
                </div>
              );
                  })}
                </>
              );
            })()}
          </div>
        </div>
      </div>
    </div>
  );
}
