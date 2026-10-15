import type {
  AnalyticsResponse,
  ChartCandle,
  DashboardResponse,
  OptionChainResponse,
  OptionUnderlying,
  UpstoxStatus,
} from "../types";

export interface LtpRow {
  strike: number;
  callLtp: number;
  callBid: number;
  callAsk: number;
  callClosePrice: number;
  putLtp: number;
  putBid: number;
  putAsk: number;
  putClosePrice: number;
}

export interface LtpResponse {
  rows: LtpRow[];
  generatedAt: string;
}

async function requestJson<T>(input: string) {
  const response = await fetch(input);
  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { error?: string };
      if (payload.error) {
        message = payload.error;
      }
    } catch {
      // Keep the default message.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export const optionsApi = {
  search(query: string) {
    return requestJson<OptionUnderlying[]>(`/api/options/search?q=${encodeURIComponent(query)}`);
  },
  getDashboard(symbol: string, expiry?: string) {
    const params = new URLSearchParams({ symbol });
    if (expiry) params.set("expiry", expiry);
    return requestJson<DashboardResponse>(`/api/options/dashboard?${params.toString()}`);
  },
  getChain(symbol: string, expiry?: string, strikeCount = 31) {
    const params = new URLSearchParams({ symbol, strikes: String(strikeCount) });
    if (expiry) params.set("expiry", expiry);
    return requestJson<OptionChainResponse>(`/api/options/chain?${params.toString()}`);
  },
  getChainLtp(symbol: string, expiry?: string) {
    const params = new URLSearchParams({ symbol });
    if (expiry) params.set("expiry", expiry);
    return requestJson<LtpResponse>(`/api/options/chain/ltp?${params.toString()}`);
  },
  getAnalytics(symbol: string, expiry?: string) {
    const params = new URLSearchParams({ symbol });
    if (expiry) params.set("expiry", expiry);
    return requestJson<AnalyticsResponse>(`/api/analytics/summary?${params.toString()}`);
  },
  getChart(symbol: string, interval = "5m", instrumentKey?: string) {
    const params = new URLSearchParams({ symbol, interval });
    if (instrumentKey) params.set("instrument_key", instrumentKey);
    return requestJson<ChartCandle[]>(`/api/options/chart?${params.toString()}`);
  },
  getUpstoxStatus() {
    return requestJson<UpstoxStatus>("/api/upstox/status");
  },
  getLedger() {
    return requestJson<import("../types").LedgerState>("/api/ledger");
  },
  async openTrade(tradeData: any) {
    const res = await fetch("/api/ledger/trade", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "OPEN", tradeData })
    });
    if (!res.ok) throw new Error("Failed to open trade");
    return (await res.json()) as import("../types").LedgerState;
  },
  async closeTrade(tradeId: string, exitPrice: number) {
    const res = await fetch("/api/ledger/trade", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "CLOSE", tradeId, exitPrice })
    });
    if (!res.ok) throw new Error("Failed to close trade");
    return (await res.json()) as import("../types").LedgerState;
  }
};

