export type Confidence = "low" | "medium" | "high";
export type OptionSide = "CE" | "PE";
export type PaperAction = "BUY_CE" | "BUY_PE" | "SELL_CE" | "SELL_PE";
export type MarketStatus = "open" | "closed" | "pre-open" | "after-hours";
export type MoneynessFilter = "ALL" | "ITM" | "ATM" | "OTM";

export interface OptionUnderlying {
  symbol: string;
  name: string;
  kind: "index" | "stock" | "commodity";
  quoteSymbol?: string;
  exchange: string;
  instrument_key?: string;
  strikeStep: number;
  lotSize: number;
  basePrice?: number;
}

export interface UnderlyingQuote {
  symbol: string;
  name: string;
  price: number;
  previousClose: number;
  change: number;
  changePercent: number;
  dayHigh: number;
  dayLow: number;
  volume: number;
  marketStatus: MarketStatus;
  timestamp: string;
}

export interface OptionLeg {
  contractSymbol: string;
  strike: number;
  type: OptionSide;
  ltp: number;
  change: number;
  changePercent: number;
  volume: number;
  oi: number;
  oiChange: number;
  bid: number;
  ask: number;
  iv: number | null;
  delta?: number | null;
  theta?: number | null;
  gamma?: number | null;
  vega?: number | null;
  spread: number;
  moneyness: "ITM" | "ATM" | "OTM";
}

export interface OptionChainRow {
  strike: number;
  call: OptionLeg;
  put: OptionLeg;
  isAtm: boolean;
}

export interface OptionChainResponse {
  underlying: OptionUnderlying;
  quote: UnderlyingQuote;
  expiries: string[];
  expiry: string;
  atmStrike: number;
  strikeStep: number;
  rows: OptionChainRow[];
  generatedAt: string;
  meta: {
    source: string;
    ivAvailable: boolean;
    cacheHit: boolean;
  };
}

export interface DashboardResponse {
  underlying: OptionUnderlying;
  quote: UnderlyingQuote;
  expiries: string[];
  expiry: string;
  atmStrike: number;
  strikeStep: number;
  generatedAt: string;
  meta: {
    source: string;
    ivAvailable: boolean;
    cacheHit: boolean;
  };
}

export interface ConfidenceMetric {
  value: string;
  confidence: Confidence;
}

export interface AnalyticsResponse {
  generatedAt: string;
  underlying: string;
  expiry: string;
  analytics: {
    pcr: ConfidenceMetric;
    maxPain: ConfidenceMetric;
    largestCallOi: ConfidenceMetric;
    largestPutOi: ConfidenceMetric;
    highestOiChange: ConfidenceMetric;
    ivSummary: ConfidenceMetric;
    supportEstimate: ConfidenceMetric;
    resistanceEstimate: ConfidenceMetric;
  };
}

export interface UpstoxStatus {
  connected: boolean;
  authMode: "none" | "env-token" | "oauth";
  userId?: string;
  broker?: string;
  message?: string;
}

export interface ChartCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface WatchlistItem {
  id: string;
  contractSymbol: string;
  underlying: string;
  expiry: string;
  strike: number;
  side: OptionSide;
  pinned: boolean;
  createdAt: string;
}

export interface ChargeBreakdown {
  brokerage: number;
  stt: number;
  exchangeCharge: number;
  gst: number;
  sebiCharge: number;
  stampDuty: number;
  total: number;
}

export interface PaperPosition {
  id: string;
  contractSymbol: string;
  underlying: string;
  expiry: string;
  strike: number;
  side: OptionSide;
  action: string;
  qty: number;
  entryPrice: number;
  exitPrice: number | null;
  grossPnl: number | null;
  netPnl: number | null;
  entryCharges: ChargeBreakdown;
  exitCharges: ChargeBreakdown | null;
  endingBalance: number | null;
  status: "OPEN" | "CLOSED";
  timestamp: string;
  exitTimestamp: string | null;
  notes: string;
}

export interface LedgerState {
  balance: number;
  totalPnl: number;
  avgProfit: number;
  latestTradePnl: number;
  trades: PaperPosition[];
  pendingSignals?: any[];
}

export interface ChainFilters {
  strikeCount: number;
  moneyness: MoneynessFilter;
  minLiquidity: number;
  strikeQuery: string;
  autoRefresh: boolean;
}
