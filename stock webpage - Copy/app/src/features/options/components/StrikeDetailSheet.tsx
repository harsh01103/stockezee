import { CircleHelp, Droplets, Scale, TrendingUp } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type { OptionChainRow } from "../types";

function explanationLabel(title: string, value: string) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <div className="mb-1 text-[11px] uppercase tracking-[0.22em] text-white/35">{title}</div>
      <div className="text-sm text-white/80">{value}</div>
    </div>
  );
}

export function StrikeDetailSheet({
  row,
  expiry,
  open,
  onOpenChange,
}: {
  row: OptionChainRow | null;
  expiry: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const expiryDate = new Date(`${expiry}T15:30:00+05:30`);
  const timeToExpiryHours = Math.max(0, (expiryDate.getTime() - Date.now()) / (1000 * 60 * 60));

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full border-white/10 bg-[#09101a] text-white sm:max-w-xl">
        <SheetHeader className="border-b border-white/10">
          <SheetTitle className="text-xl">Strike {row?.strike ?? "-"}</SheetTitle>
          <SheetDescription>
            CE and PE snapshot with liquidity and positioning context.
          </SheetDescription>
        </SheetHeader>

        {row && (
          <div className="flex-1 space-y-6 overflow-y-auto p-5">
            <div className="grid gap-4 sm:grid-cols-2">
              {[row.call, row.put].map((leg) => (
                <div key={leg.contractSymbol} className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
                  <div className="mb-2 flex items-center justify-between">
                    <div className="text-sm font-semibold text-white">{leg.type}</div>
                    <div className="rounded-full border border-white/10 px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-white/50">
                      {leg.moneyness}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <div className="text-white/35">Premium</div>
                      <div className="font-semibold">₹{leg.ltp.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-white/35">Spread</div>
                      <div className="font-semibold">₹{leg.spread.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-white/35">Volume</div>
                      <div className="font-semibold">{leg.volume.toLocaleString("en-IN")}</div>
                    </div>
                    <div>
                      <div className="text-white/35">OI</div>
                      <div className="font-semibold">{leg.oi.toLocaleString("en-IN")}</div>
                    </div>
                    <div>
                      <div className="text-white/35">OI Change</div>
                      <div className="font-semibold">{leg.oiChange.toLocaleString("en-IN")}</div>
                    </div>
                    <div>
                      <div className="text-white/35">Bid / Ask</div>
                      <div className="font-semibold">₹{leg.bid.toFixed(2)} / ₹{leg.ask.toFixed(2)}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              {explanationLabel("High OI", "More traders are concentrated here, so this strike often matters structurally.")}
              {explanationLabel("Low Spread", "Tighter bid/ask usually means easier entry and exit in a paper-sim context.")}
              {explanationLabel("High Volume", "Recent activity is stronger, which improves comparison quality across strikes.")}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
                <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
                  <TrendingUp className="h-4 w-4 text-emerald-300" />
                  Quick read
                </div>
                <div className="space-y-2 text-sm text-white/65">
                  <p>Time to expiry: {timeToExpiryHours.toFixed(1)} hours</p>
                  <p>Premium gap: ₹{Math.abs(row.call.ltp - row.put.ltp).toFixed(2)}</p>
                  <p>Combined volume: {(row.call.volume + row.put.volume).toLocaleString("en-IN")}</p>
                </div>
              </div>
              <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
                <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
                  <CircleHelp className="h-4 w-4 text-sky-300" />
                  What this means
                </div>
                <div className="space-y-2 text-sm text-white/65">
                  <p className="flex items-center gap-2"><Scale className="h-4 w-4" /> Compare CE and PE OI to see where positioning leans.</p>
                  <p className="flex items-center gap-2"><Droplets className="h-4 w-4" /> Lower spreads and higher volume improve contract quality.</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
