import { useEffect, useMemo, useRef } from "react";
import { createChart, CandlestickSeries, ColorType, HistogramSeries, LineSeries } from "lightweight-charts";
import type { UTCTimestamp, IChartApi } from "lightweight-charts";
import { EMA, RSI, VWAP } from "technicalindicators";
import type { ChartCandle } from "../types";

function toLineData(candles: ChartCandle[], values: number[]) {
  const offset = candles.length - values.length;
  if (offset < 0) return [];
  return values.map((value, index) => ({ time: candles[index + offset].time as UTCTimestamp, value }));
}

export function OptionsChartPanel({
  candles,
  atmStrike,
  strikeMarkers = [],
  overlays,
  chartLabel,
  height,
}: {
  candles: ChartCandle[];
  atmStrike?: number;
  strikeMarkers?: number[];
  overlays: { ema: boolean; vwap: boolean; rsi: boolean; volume: boolean };
  chartLabel?: string;
  height?: number;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<any>({});
  const hasFitContent = useRef(false);

  const annotation = useMemo(
    () => `${strikeMarkers.slice(0, 3).join(" ? ")}${strikeMarkers.length > 3 ? " ? ..." : ""}`,
    [strikeMarkers]
  );

  // Initialize chart exactly once (or when overlays/height config changes)
  useEffect(() => {
    if (!hostRef.current) return;

    const chart = createChart(hostRef.current, {
      layout: { background: { type: ColorType.Solid, color: "#08111d" }, textColor: "#9db0c7" },
      grid: { vertLines: { color: "#162130" }, horzLines: { color: "#162130" } },
      width: hostRef.current.clientWidth,
      height: height || (window.innerWidth < 768 ? 340 : 520),
      crosshair: { mode: 1 },
      leftPriceScale: { visible: overlays.rsi, borderColor: "#162130" },
      rightPriceScale: { visible: true, borderColor: "#162130" },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: (time: number, tickMarkType: any) => {
          const dt = new Date(time * 1000);
          if (tickMarkType === 0) {
            return dt.toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata", year: "numeric" });
          } else if (tickMarkType === 1 || tickMarkType === 2) {
            return dt.toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata", month: "short", day: "numeric" });
          } else {
            return dt.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: true });
          }
        },
      },
      localization: {
        timeFormatter: (time: number) => {
          return new Intl.DateTimeFormat("en-IN", {
            timeZone: "Asia/Kolkata",
            hour: "numeric",
            minute: "numeric",
            year: "numeric",
            month: "short",
            day: "numeric",
          }).format(new Date(time * 1000));
        },
      },
    });
    chartRef.current = chart;
    hasFitContent.current = false; // Reset fitContent tracker for new chart

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#2dd4bf",
      downColor: "#fb7185",
      borderVisible: false,
      wickUpColor: "#2dd4bf",
      wickDownColor: "#fb7185",
    });
    const emaSeries = chart.addSeries(LineSeries, { color: "#f59e0b", lineWidth: 2, visible: overlays.ema });
    const vwapSeries = chart.addSeries(LineSeries, { color: "#38bdf8", lineWidth: 2, visible: overlays.vwap });
    const rsiSeries = chart.addSeries(LineSeries, { color: "#a78bfa", lineWidth: 2, visible: overlays.rsi, priceScaleId: "left" });
    const volumeSeries = chart.addSeries(HistogramSeries, { visible: overlays.volume, priceScaleId: "", priceFormat: { type: "volume" } });
    chart.priceScale("").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

    seriesRef.current = { candleSeries, emaSeries, vwapSeries, rsiSeries, volumeSeries };

    const resize = () => {
      if (!hostRef.current) return;
      chart.applyOptions({
        width: hostRef.current.clientWidth,
        height: height || (window.innerWidth < 768 ? 340 : 520),
      });
    };
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
      chartRef.current = null;
    };
  }, [overlays.ema, overlays.rsi, overlays.volume, overlays.vwap, height]);

  // Update data efficiently without destroying the chart
  useEffect(() => {
    if (!chartRef.current || !seriesRef.current.candleSeries || candles.length === 0) return;

    const { candleSeries, emaSeries, vwapSeries, rsiSeries, volumeSeries } = seriesRef.current;

    candleSeries.setData(
      candles.map((candle) => ({
        ...candle,
        time: candle.time as UTCTimestamp,
      }))
    );
    volumeSeries.setData(
      candles.map((candle) => ({
        time: candle.time as UTCTimestamp,
        value: candle.volume,
        color: candle.close >= candle.open ? "#2dd4bf66" : "#fb718566",
      }))
    );

    const closes = candles.map((candle) => candle.close);
    const highs = candles.map((candle) => candle.high);
    const lows = candles.map((candle) => candle.low);
    const volumes = candles.map((candle) => candle.volume);

    emaSeries.setData(toLineData(candles, EMA.calculate({ period: 20, values: closes })));
    const hasVolume = volumes.some((v) => v > 0);
    if (hasVolume) {
      vwapSeries.setData(toLineData(candles, VWAP.calculate({ close: closes, high: highs, low: lows, volume: volumes })));
    }
    rsiSeries.setData(toLineData(candles, RSI.calculate({ period: 14, values: closes })));

    // Handle price lines
    const isOptionChart = chartLabel?.includes(" CE") || chartLabel?.includes(" PE");
    if (!isOptionChart && atmStrike) {
      // Clear existing lines by recreating the series or managing an array of line objects if we want to be fully optimal
      // But creating price lines is relatively cheap compared to recreating the entire chart
      candleSeries.createPriceLine({
        price: atmStrike,
        color: "#22c55e",
        lineWidth: 1,
        axisLabelVisible: true,
        title: "ATM",
        lineStyle: 2,
      });

      strikeMarkers.slice(0, 5).forEach((strike, index) => {
        candleSeries.createPriceLine({
          price: strike,
          color: index === 0 ? "#f97316" : "#475569",
          lineWidth: 1,
          axisLabelVisible: false,
          title: index === 0 ? "Pinned" : "",
          lineStyle: 4,
        });
      });
    }

    // Only fit content on the very first data load, allowing user zoom state to persist afterwards
    if (!hasFitContent.current) {
      chartRef.current.timeScale().fitContent();
      hasFitContent.current = true;
    }
  }, [candles, atmStrike, strikeMarkers, chartLabel]);

  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-sm font-semibold text-white">{chartLabel || "Underlying chart"}</div>
          <div className="text-xs text-white/40">Candlestick, volume, EMA, VWAP, RSI, and strike markers</div>
        </div>
        <div className="text-xs text-white/45">ATM {atmStrike} {annotation ? `? Markers ${annotation}` : ""}</div>
      </div>
      <div ref={hostRef} className="w-full overflow-hidden rounded-2xl border border-white/10" />
    </div>
  );
}
