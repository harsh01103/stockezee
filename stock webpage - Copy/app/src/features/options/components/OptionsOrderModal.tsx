import { useState, useEffect } from "react";
import type { OptionChainRow, PaperPosition } from "../types";
import { X } from "lucide-react";

export function OptionsOrderModal({
  isOpen,
  onClose,
  row,
  side,
  action,
  underlying,
  expiry,
  onSubmit,
}: {
  isOpen: boolean;
  onClose: () => void;
  row: OptionChainRow | null;
  side: "CE" | "PE";
  action: "BUY" | "SELL";
  underlying: string;
  expiry: string;
  onSubmit: (position: Omit<PaperPosition, "id" | "createdAt" | "pnl">) => void;
}) {
  const [qty, setQty] = useState(1);
  const [orderType, setOrderType] = useState<"MARKET" | "LIMIT">("MARKET");
  const [productType, setProductType] = useState<"INTRADAY" | "DELIVERY">("INTRADAY");
  const [limitPrice, setLimitPrice] = useState<number>(0);

  useEffect(() => {
    if (row) {
      setLimitPrice(side === "CE" ? row.call.ltp : row.put.ltp);
    }
  }, [row, side]);

  if (!isOpen || !row) return null;

  const leg = side === "CE" ? row.call : row.put;
  const lotSize = underlying === "NIFTY" ? 65 : underlying === "BANKNIFTY" ? 30 : 1;
  const totalShares = qty * lotSize;
  const price = orderType === "MARKET" ? leg.ltp : limitPrice;
  const cost = price * totalShares;
  const brokerage = 20;
  const exchangeCharge = cost * 0.0003503;
  const stt = action === "SELL" ? cost * 0.00125 : 0;
  const sebiCharge = cost * 0.000001;
  const stampDuty = action === "BUY" ? cost * 0.00003 : 0;
  const gst = (brokerage + exchangeCharge + sebiCharge) * 0.18;
  const taxes = brokerage + exchangeCharge + stt + sebiCharge + stampDuty + gst;
  const marginReq = cost + taxes;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-[#0f1115] shadow-2xl overflow-hidden">
        {/* Header */}
        <div className={`px-5 py-4 flex justify-between items-center border-b border-white/5 ${action === 'BUY' ? 'bg-emerald-500/10' : 'bg-red-500/10'}`}>
          <div>
            <div className="text-sm font-bold text-white/50 uppercase tracking-wider">{action} {leg.contractSymbol}</div>
            <div className="text-xl font-bold text-white">{underlying} {expiry} {row.strike} {side}</div>
          </div>
          <button onClick={onClose} className="text-white/40 hover:text-white transition-colors">
            <X className="h-6 w-6" />
          </button>
        </div>

        <div className="p-5 space-y-6">
          {/* Top Toggles */}
          <div className="flex gap-2">
            <div className="flex flex-1 rounded-lg bg-black/40 p-1 border border-white/5">
              <button onClick={() => setProductType("INTRADAY")} className={`flex-1 rounded-md py-1.5 text-xs font-bold transition-colors ${productType === "INTRADAY" ? "bg-white/10 text-white" : "text-white/40 hover:text-white"}`}>MIS (Intraday)</button>
              <button onClick={() => setProductType("DELIVERY")} className={`flex-1 rounded-md py-1.5 text-xs font-bold transition-colors ${productType === "DELIVERY" ? "bg-white/10 text-white" : "text-white/40 hover:text-white"}`}>NRML (Overnight)</button>
            </div>
            <div className="flex flex-1 rounded-lg bg-black/40 p-1 border border-white/5">
              <button onClick={() => setOrderType("MARKET")} className={`flex-1 rounded-md py-1.5 text-xs font-bold transition-colors ${orderType === "MARKET" ? "bg-white/10 text-white" : "text-white/40 hover:text-white"}`}>Market</button>
              <button onClick={() => setOrderType("LIMIT")} className={`flex-1 rounded-md py-1.5 text-xs font-bold transition-colors ${orderType === "LIMIT" ? "bg-white/10 text-white" : "text-white/40 hover:text-white"}`}>Limit</button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Qty */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Qty (Lots)</label>
              <input
                type="number"
                min="1"
                value={qty}
                onChange={(e) => setQty(parseInt(e.target.value) || 1)}
                className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-lg font-bold text-white outline-none focus:border-white/30"
              />
            </div>
            {/* Price */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Price</label>
              <input
                type="number"
                disabled={orderType === "MARKET"}
                value={orderType === "MARKET" ? leg.ltp : limitPrice}
                onChange={(e) => setLimitPrice(parseFloat(e.target.value) || 0)}
                className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-lg font-bold text-white outline-none focus:border-white/30 disabled:opacity-50"
              />
            </div>
          </div>

          {/* Real-time Bid/Ask */}
          <div className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] px-4 py-2">
            <div className="text-xs">
              <span className="text-white/40">Bid </span>
              <span className="font-mono text-emerald-400">{leg.bid.toFixed(2)}</span>
            </div>
            <div className="text-xs font-bold text-white/20">LTP {leg.ltp.toFixed(2)}</div>
            <div className="text-xs">
              <span className="text-white/40">Ask </span>
              <span className="font-mono text-red-400">{leg.ask.toFixed(2)}</span>
            </div>
          </div>

          {/* Footer actions */}
          <div className="flex items-center justify-between pt-2">
            <div>
              <div className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Margin Required</div>
              <div className="flex items-baseline gap-2">
                <div className="text-lg font-bold text-white">₹{marginReq.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</div>
                <div className="text-[10px] font-medium text-white/40">
                  (₹{cost.toLocaleString("en-IN", { maximumFractionDigits: 2 })} + ₹{taxes.toLocaleString("en-IN", { maximumFractionDigits: 2 })})
                </div>
              </div>
            </div>
            <button
              onClick={() => {
                onSubmit({
                  contractSymbol: leg.contractSymbol,
                  underlying,
                  expiry,
                  strike: row.strike,
                  side,
                  action,
                  qty: qty * lotSize,
                  entry: orderType === "MARKET" ? leg.ltp : limitPrice,
                  exit: null,
                  notes: `${productType} | ${orderType}`,
                });
                onClose();
              }}
              className={`rounded-xl px-8 py-3 text-sm font-bold uppercase tracking-widest text-white shadow-lg transition-all hover:-translate-y-0.5 ${
                action === "BUY" ? "bg-emerald-500 hover:bg-emerald-400 hover:shadow-emerald-500/25" : "bg-red-500 hover:bg-red-400 hover:shadow-red-500/25"
              }`}
            >
              {action}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
