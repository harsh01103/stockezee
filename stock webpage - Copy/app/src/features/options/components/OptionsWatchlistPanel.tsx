import { Pin, Trash2 } from "lucide-react";
import type { WatchlistItem } from "../types";

export function OptionsWatchlistPanel({
  items,
  onTogglePin,
  onRemove,
}: {
  items: WatchlistItem[];
  onTogglePin: (id: string) => void;
  onRemove: (id: string) => void;
}) {
  if (items.length === 0) {
    return (
      <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-8 text-center text-sm font-medium text-white/40 shadow-2xl backdrop-blur-xl">
        Watchlist is empty. Add strikes from the Option Chain.
      </div>
    );
  }

  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.03] overflow-hidden shadow-2xl backdrop-blur-xl">
      <div className="divide-y divide-white/10">
        {items.map((item) => (
          <div key={item.id} className="flex items-center justify-between p-4 hover:bg-white/[0.04] transition-colors">
            <div>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${item.side === "CE" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"}`}>
                  {item.side}
                </span>
                <span className="text-sm font-bold text-white">{item.contractSymbol}</span>
              </div>
              <div className="mt-1 text-xs font-medium text-white/40">
                {item.underlying} • {item.expiry} • {item.strike}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => onTogglePin(item.id)}
                className={`p-2 rounded-full hover:bg-white/10 transition-colors ${item.pinned ? "text-emerald-400" : "text-white/40"}`}
                title={item.pinned ? "Unpin from chart" : "Pin to chart"}
              >
                <Pin className="h-4 w-4" />
              </button>
              <button
                onClick={() => onRemove(item.id)}
                className="p-2 rounded-full hover:bg-white/10 text-white/40 hover:text-red-400 transition-colors"
                title="Remove from watchlist"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
