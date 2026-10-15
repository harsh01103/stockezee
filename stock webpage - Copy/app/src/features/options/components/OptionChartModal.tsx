import * as DialogPrimitive from "@radix-ui/react-dialog";
import { OptionsChartPanel } from "./OptionsChartPanel";
import { useEffect, useState } from "react";
import { optionsApi } from "../services/optionsApi";
import type { ChartCandle } from "../types";

interface OptionChartModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  symbol: string;
  instrumentKey?: string;
}

export function OptionChartModal({ isOpen, onClose, title, symbol, instrumentKey }: OptionChartModalProps) {
  const [chartData, setChartData] = useState<ChartCandle[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    let active = true;
    setLoading(true);
    setError(null);
    setChartData([]);

    optionsApi
      .getChart(symbol, "1m", instrumentKey)
      .then((data) => {
        if (!active) return;
        setChartData(data);
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message || "Failed to load chart");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [isOpen, symbol, instrumentKey]);

  return (
    <DialogPrimitive.Root open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content
          className="fixed left-[30%] top-16 z-50 w-[550px] transform -translate-x-1/2 overflow-hidden rounded-xl border border-white/10 bg-[#0c1420] shadow-2xl data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 outline-none"
        >
          <div className="p-4 min-h-[400px] flex flex-col bg-[#0c1420]">
            {loading ? (
              <div className="flex-1 flex items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
              </div>
            ) : error ? (
              <div className="flex-1 flex items-center justify-center text-red-400">
                {error}
              </div>
            ) : chartData.length > 0 ? (
              <div className="flex-1 -m-4">
                <OptionsChartPanel
                  candles={chartData}
                  chartLabel={title}
                  height={400}
                  atmStrike={0}
                  strikeMarkers={[]}
                  overlays={{ ema: false, vwap: false, rsi: false, volume: true }}
                />
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-white/40">
                No chart data available
              </div>
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
