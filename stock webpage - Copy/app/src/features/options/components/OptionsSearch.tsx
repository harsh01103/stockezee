import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { optionsApi } from "../services/optionsApi";
import type { OptionUnderlying } from "../types";
import { useDebouncedValue } from "../hooks/useDebouncedValue";

interface OptionsSearchProps {
  value: string;
  onSelect: (underlying: OptionUnderlying) => void;
}

export function OptionsSearch({ value, onSelect }: OptionsSearchProps) {
  const [query, setQuery] = useState(value);
  const [items, setItems] = useState<OptionUnderlying[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const debounced = useDebouncedValue(query, 80);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    optionsApi
      .search(debounced || "N")
      .then((data) => {
        if (!active) return;
        setItems(data);
      })
      .catch(() => {
        if (!active) return;
        setItems([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [debounced]);

  return (
    <div className="relative w-full" ref={containerRef}>
      <div className="flex h-12 items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.03] px-4 shadow-[0_20px_80px_rgba(0,0,0,0.25)] backdrop-blur-xl">
        <Search className="h-4 w-4 text-white/45" />
        <input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder="Search NIFTY, BANKNIFTY, CRUDEOIL"
          className="h-full w-full bg-transparent text-sm font-medium text-white outline-none placeholder:text-white/35"
        />
      </div>

      {open && (
        <div className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-40 overflow-hidden rounded-2xl border border-white/10 bg-[#09101a] shadow-[0_20px_80px_rgba(0,0,0,0.5)]">
          <div className="border-b border-white/5 px-4 py-2 text-[10px] uppercase tracking-[0.22em] text-white/35">
            Contracts
          </div>
          <div className="max-h-72 overflow-y-auto">
            {loading ? (
              <div className="px-4 py-4 text-sm text-white/40">Searching...</div>
            ) : items.length === 0 ? (
              <div className="px-4 py-4 text-sm text-white/40">No contracts found.</div>
            ) : (
              items.map((item) => (
                <button
                  key={item.symbol}
                  onClick={() => {
                    onSelect(item);
                    setQuery(item.symbol);
                    setOpen(false);
                  }}
                  className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-white/[0.03]"
                >
                  <div>
                    <div className="text-sm font-bold text-white">{item.symbol}</div>
                    <div className="text-xs text-white/40">{item.name}</div>
                  </div>
                  <div className="flex items-center gap-1 rounded-full border border-white/10 px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-white/50">
                    {item.kind}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
