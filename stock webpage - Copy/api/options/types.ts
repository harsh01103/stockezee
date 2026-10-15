export type UnderlyingKind = "index" | "stock";

export interface OptionUnderlying {
  symbol: string;
  name: string;
  kind: UnderlyingKind;
  quoteSymbol: string;
  exchange: string;
  strikeStep: number;
  lotSize: number;
  basePrice: number;
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
  marketStatus: "open" | "closed" | "pre-open" | "after-hours";
  timestamp: string;
}

export interface OptionLeg {
  contractSymbol: string;
  strike: number;
  type: "CE" | "PE";
  ltp: number;
  change: number;
  changePercent: number;
  volume: number;
  oi: number;
  oiChange: number;
  bid: number;
  ask: number;
  iv: number | null;
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
    source: "generated-research";
    ivAvailable: boolean;
    cacheHit: boolean;
  };
}

export interface ConfidenceMetric {
  value: string;
  confidence: "low" | "medium" | "high";
}

export interface AnalyticsSummary {
  pcr: ConfidenceMetric;
  maxPain: ConfidenceMetric;
  largestCallOi: ConfidenceMetric;
  largestPutOi: ConfidenceMetric;
  highestOiChange: ConfidenceMetric;
  ivSummary: ConfidenceMetric;
  supportEstimate: ConfidenceMetric;
  resistanceEstimate: ConfidenceMetric;
}

export interface ChartCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}
