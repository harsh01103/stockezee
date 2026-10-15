
import { useState, useEffect } from "react";
import type { OptionChainRow, PaperPosition } from "../types";

export function OptionsPaperTradePanel({
  selectedRow,
  underlying,
  expiry,
  positions,
  rows,
  initialSide = "CE",
  onCreate,
  onClose,
}: {
  selectedRow: OptionChainRow | null;
  underlying: string;
  expiry: string;
  positions: PaperPosition[];
  rows: OptionChainRow[];
  initialSide?: "CE" | "PE";
  onCreate: (position: Omit<PaperPosition, "id" | "createdAt" | "pnl">) => void;
  onClose: (id: string, exit: number) => void;
}) {
  const [qty, setQty] = useState(1);
  const [side, setSide] = useState<"CE" | "PE">(initialSide);

  // Sync side if initialSide changes when user clicks quick trade
  useEffect(() => {
    setSide(initialSide);
  }, [initialSide]);

  const activePosition = selectedRow
    ? positions.find(
        (p) =>
          p.contractSymbol === selectedRow[side === "CE" ? "call" : "put"].contractSymbol &&
          p.exit === null
      )
    : null;

  let marginReq = 0;
  let orderCost = 0;
  let orderTaxes = 0;
  if (selectedRow) {
    const leg = side === "CE" ? selectedRow.call : selectedRow.put;
    const lotSize = underlying === "NIFTY" ? 65 : underlying === "BANKNIFTY" ? 30 : 1;
    orderCost = leg.ltp * qty * lotSize;
    const brokerage = 20;
    const exchangeCharge = orderCost * 0.0003503;
    const sebiCharge = orderCost * 0.000001;
    const stampDuty = orderCost * 0.00003; // assuming buy
    const gst = (brokerage + exchangeCharge + sebiCharge) * 0.18;
    orderTaxes = brokerage + exchangeCharge + sebiCharge + stampDuty + gst;
    marginReq = orderCost + orderTaxes;
  }

  return (
    <div className="grid gap-6 md:grid-cols-[380px_1fr]">
      {/* Order Window */}
      <div className="rounded-3xl border border-white/10 bg-white/[0.03] shadow-2xl backdrop-blur-xl">
        <div className="border-b border-white/10 p-5 text-lg font-bold text-white">
          Order Window
        </div>
        
        {selectedRow ? (
          <div className="p-5 space-y-6">
            <div className="text-sm font-semibold text-white/50">
              {underlying} {expiry} <span className="text-white">{selectedRow.strike}</span>
            </div>

            <div className="flex rounded-lg bg-black/20 p-1 border border-white/5">
              <button
                onClick={() => setSide("CE")}
                className={`flex-1 rounded-md py-2 text-sm font-bold transition-all ${
                  side === "CE" ? "bg-white/10 text-white shadow-sm" : "text-white/40 hover:text-white hover:bg-white/5"
                }`}
              >
                Call (CE)
              </button>
              <button
                onClick={() => setSide("PE")}
                className={`flex-1 rounded-md py-2 text-sm font-bold transition-all ${
                  side === "PE" ? "bg-white/10 text-white shadow-sm" : "text-white/40 hover:text-white hover:bg-white/5"
                }`}
              >
                Put (PE)
              </button>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-white/50 uppercase tracking-widest">Quantity (Lots)</label>
              <div className="flex items-center overflow-hidden rounded-lg border border-white/10 bg-black/20 transition-colors focus-within:border-white/20">
                <button
                  onClick={() => setQty(Math.max(1, qty - 1))}
                  className="px-4 py-3 text-white/40 hover:bg-white/5 hover:text-white"
                >-</button>
                <input
                  type="number"
                  min="1"
                  value={qty}
                  onChange={(e) => setQty(parseInt(e.target.value) || 1)}
                  className="w-full bg-transparent text-center text-lg font-bold text-white outline-none"
                />
                <button
                  onClick={() => setQty(qty + 1)}
                  className="px-4 py-3 text-white/40 hover:bg-white/5 hover:text-white"
                >+</button>
              </div>
            </div>

            <div className="flex justify-between items-center rounded-lg bg-black/20 px-4 py-3 border border-white/5">
              <span className="text-sm font-medium text-white/50">Margin Required</span>
              <div className="flex items-baseline gap-2">
                <span className="text-lg font-bold text-white">
                  ₹{marginReq.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                </span>
                <span className="text-[10px] font-medium text-white/40">
                  (₹{orderCost.toLocaleString("en-IN", { maximumFractionDigits: 2 })} + ₹{orderTaxes.toLocaleString("en-IN", { maximumFractionDigits: 2 })})
                </span>
              </div>
            </div>

            {activePosition ? (
              <button
                onClick={() => onClose(activePosition.id, side === "CE" ? selectedRow.call.ltp : selectedRow.put.ltp)}
                className="w-full rounded-xl bg-red-500 py-4 text-sm font-bold uppercase tracking-widest text-white shadow-[0_0_20px_rgba(239,68,68,0.4)] transition-all hover:bg-red-400 hover:shadow-[0_0_30px_rgba(239,68,68,0.6)]"
              >
                Exit Position
              </button>
            ) : (
              <div className="grid grid-cols-2 gap-4">
                <button
                  onClick={() =>
                    onCreate({
                      contractSymbol: selectedRow[side === "CE" ? "call" : "put"].contractSymbol,
                      underlying,
                      expiry,
                      strike: selectedRow.strike,
                      side,
                      action: "BUY",
                      qty: qty * (underlying === "NIFTY" ? 65 : underlying === "BANKNIFTY" ? 30 : 1),
                      entry: selectedRow[side === "CE" ? "call" : "put"].ltp,
                      exit: null,
                      notes: "",
                    })
                  }
                  className="w-full rounded-xl bg-emerald-500 py-4 text-sm font-bold uppercase tracking-widest text-white shadow-[0_0_20px_rgba(16,185,129,0.4)] transition-all hover:bg-emerald-400 hover:shadow-[0_0_30px_rgba(16,185,129,0.6)]"
                >
                  Buy
                </button>
                <button
                  onClick={() =>
                    onCreate({
                      contractSymbol: selectedRow[side === "CE" ? "call" : "put"].contractSymbol,
                      underlying,
                      expiry,
                      strike: selectedRow.strike,
                      side,
                      action: "SELL",
                      qty: qty * (underlying === "NIFTY" ? 65 : underlying === "BANKNIFTY" ? 30 : 1),
                      entry: selectedRow[side === "CE" ? "call" : "put"].ltp,
                      exit: null,
                      notes: "",
                    })
                  }
                  className="w-full rounded-xl bg-red-500 py-4 text-sm font-bold uppercase tracking-widest text-white shadow-[0_0_20px_rgba(239,68,68,0.4)] transition-all hover:bg-red-400 hover:shadow-[0_0_30px_rgba(239,68,68,0.6)]"
                >
                  Sell
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="p-12 text-center text-sm font-medium text-white/40">
            Select a strike from the Option Chain to place an order.
          </div>
        )}
      </div>

      {/* Positions Table */}
      <div className="rounded-3xl border border-white/10 bg-white/[0.03] shadow-2xl backdrop-blur-xl overflow-hidden">
        <div className="border-b border-white/10 p-5 text-lg font-bold text-white bg-white/[0.02]">
          Positions
        </div>
        <div className="p-0">
          {positions.length === 0 ? (
            <div className="p-12 text-center text-sm font-medium text-white/40">
              No paper positions.
            </div>
          ) : (
            <div className="divide-y divide-[#2a2a2a]">
              {positions.map((pos) => {
                const isOpen = pos.exit === null;
                
                // Live PnL calculation
                let liveLtp = 0;
                if (isOpen) {
                  const chainRow = rows.find(r => r.strike === pos.strike);
                  if (chainRow) {
                    liveLtp = pos.side === "CE" ? chainRow.call.ltp : chainRow.put.ltp;
                  }
                }
                
                const longPosition = pos.action === "BUY";
                const pnl = isOpen 
                  ? (liveLtp ? (longPosition ? (liveLtp - pos.entry) : (pos.entry - liveLtp)) * pos.qty : 0)
                  : pos.pnl;

                const pnlTone = pnl && pnl > 0 ? "text-emerald-400" : pnl && pnl < 0 ? "text-red-400" : "text-white/60";
                
                return (
                  <div key={pos.id} className="p-4 flex items-center justify-between bg-white/[0.02] hover:bg-white/[0.04] transition-colors border-b border-white/5 last:border-0">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${pos.action === "BUY" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"}`}>
                          {pos.action}
                        </span>
                        <span className="text-sm font-bold text-white">{pos.contractSymbol}</span>
                      </div>
                      <div className="mt-1 text-xs font-medium text-white/50">
                        {pos.qty} Qty • Entry ₹{pos.entry.toFixed(2)} {pos.exit ? `• Exit ₹${pos.exit.toFixed(2)}` : (liveLtp ? `• Live ₹${liveLtp.toFixed(2)}` : "")}
                      </div>
                    </div>
                    <div className="text-right flex items-center gap-4">
                      <div>
                        <div className={`text-sm font-bold ${pnlTone}`}>
                          {pnl! > 0 ? "+" : ""}₹{pnl?.toFixed(2)}
                        </div>
                        <div className="text-[10px] font-semibold text-white/40 uppercase tracking-widest">{isOpen ? "Live PnL" : "Closed PnL"}</div>
                      </div>
                      {isOpen && liveLtp > 0 && (
                        <button
                          onClick={() => onClose(pos.id, liveLtp)}
                          className="px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 text-xs font-bold uppercase tracking-wider hover:bg-red-500/20 transition-colors"
                        >
                          Close
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
