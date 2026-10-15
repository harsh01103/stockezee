import fetch from "node-fetch";
import type { ChartCandle, OptionUnderlying, UnderlyingQuote } from "../options/types";
import { getMarketStatus } from "../options/utils";

const quoteCache = new Map<string, { expiresAt: number; value: UnderlyingQuote }>();
const candleCache = new Map<string, { expiresAt: number; value: ChartCandle[] }>();

function buildFallbackQuote(underlying: OptionUnderlying): UnderlyingQuote {
  const price = underlying.basePrice;
  const previousClose = price * 0.996;
  const change = price - previousClose;

  return {
    symbol: underlying.symbol,
    name: underlying.name,
    price,
    previousClose,
    change,
    changePercent: (change / previousClose) * 100,
    dayHigh: price * 1.007,
    dayLow: price * 0.993,
    volume: Math.round(price * 180),
    marketStatus: getMarketStatus(),
    timestamp: new Date().toISOString(),
  };
}

export async function getUnderlyingQuote(
  underlying: OptionUnderlying
): Promise<UnderlyingQuote> {
  const cached = quoteCache.get(underlying.symbol);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.value;
  }

  try {
    const response = await fetch(
      `https://query1.finance.yahoo.com/v8/finance/chart/${underlying.quoteSymbol}?interval=1m&range=1d`,
      { headers: { "User-Agent": "Mozilla/5.0" } }
    );
    const payload = (await response.json()) as {
      chart?: { result?: Array<{ meta?: Record<string, number> }> };
    };
    const meta = payload.chart?.result?.[0]?.meta;
    if (!meta) {
      throw new Error("missing quote metadata");
    }

    const price = meta.regularMarketPrice ?? underlying.basePrice;
    const previousClose = meta.previousClose ?? price;
    const change = price - previousClose;
    const quote: UnderlyingQuote = {
      symbol: underlying.symbol,
      name: underlying.name,
      price,
      previousClose,
      change,
      changePercent: previousClose ? (change / previousClose) * 100 : 0,
      dayHigh: meta.regularMarketDayHigh ?? price,
      dayLow: meta.regularMarketDayLow ?? price,
      volume: meta.regularMarketVolume ?? Math.round(price * 180),
      marketStatus: getMarketStatus(),
      timestamp: new Date().toISOString(),
    };

    quoteCache.set(underlying.symbol, { expiresAt: Date.now() + 15_000, value: quote });
    return quote;
  } catch {
    const fallback = buildFallbackQuote(underlying);
    quoteCache.set(underlying.symbol, { expiresAt: Date.now() + 15_000, value: fallback });
    return fallback;
  }
}

export async function getUnderlyingCandles(
  underlying: OptionUnderlying,
  interval = "5m"
): Promise<ChartCandle[]> {
  const cacheKey = `${underlying.symbol}:${interval}`;
  const cached = candleCache.get(cacheKey);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.value;
  }

  const range =
    interval === "1m" ? "5d" : interval === "1d" ? "6mo" : interval === "15m" ? "1mo" : "5d";

  try {
    const response = await fetch(
      `https://query1.finance.yahoo.com/v8/finance/chart/${underlying.quoteSymbol}?interval=${interval}&range=${range}`,
      { headers: { "User-Agent": "Mozilla/5.0" } }
    );
    const payload = (await response.json()) as {
      chart?: {
        result?: Array<{
          timestamp?: number[];
          indicators?: {
            quote?: Array<{
              open?: Array<number | null>;
              high?: Array<number | null>;
              low?: Array<number | null>;
              close?: Array<number | null>;
              volume?: Array<number | null>;
            }>;
          };
        }>;
      };
    };

    const result = payload.chart?.result?.[0];
    const timestamps = result?.timestamp ?? [];
    const quote = result?.indicators?.quote?.[0];
    if (!quote) {
      throw new Error("missing candle payload");
    }

    const candles = timestamps.flatMap((time, index) => {
      const open = quote.open?.[index];
      const high = quote.high?.[index];
      const low = quote.low?.[index];
      const close = quote.close?.[index];
      if ([open, high, low, close].some((value) => value == null)) {
        return [];
      }

      return [
        {
          time,
          open: open as number,
          high: high as number,
          low: low as number,
          close: close as number,
          volume: quote.volume?.[index] ?? 0,
        },
      ];
    });

    candleCache.set(cacheKey, { expiresAt: Date.now() + 30_000, value: candles });
    return candles;
  } catch {
    const base = underlying.basePrice;
    const candles = Array.from({ length: 72 }, (_, index) => {
      const time = Math.floor(Date.now() / 1000) - (72 - index) * 300;
      const drift = Math.sin(index / 7) * base * 0.003;
      const open = base + drift;
      const close = open + Math.cos(index / 5) * base * 0.0015;
      const high = Math.max(open, close) + base * 0.001;
      const low = Math.min(open, close) - base * 0.001;
      return {
        time,
        open,
        high,
        low,
        close,
        volume: Math.round(base * 100 + index * 25),
      };
    });
    candleCache.set(cacheKey, { expiresAt: Date.now() + 30_000, value: candles });
    return candles;
  }
}
