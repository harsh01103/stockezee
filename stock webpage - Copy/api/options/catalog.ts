import type { OptionUnderlying } from "./types";

export const OPTION_UNDERLYINGS: OptionUnderlying[] = [
  {
    symbol: "NIFTY",
    name: "NIFTY 50",
    kind: "index",
    quoteSymbol: "^NSEI",
    exchange: "NSE_INDEX",
    strikeStep: 50,
    lotSize: 50,
    basePrice: 24850,
  },
  {
    symbol: "BANKNIFTY",
    name: "NIFTY BANK",
    kind: "index",
    quoteSymbol: "^NSEBANK",
    exchange: "NSE_INDEX",
    strikeStep: 100,
    lotSize: 30,
    basePrice: 53600,
  },
  {
    symbol: "FINNIFTY",
    name: "NIFTY FIN SERVICE",
    kind: "index",
    quoteSymbol: "^CNXFIN",
    exchange: "NSE_INDEX",
    strikeStep: 50,
    lotSize: 40,
    basePrice: 24750,
  },
  {
    symbol: "RELIANCE",
    name: "Reliance Industries Limited",
    kind: "stock",
    quoteSymbol: "RELIANCE.NS",
    exchange: "NSE_EQ",
    strikeStep: 20,
    lotSize: 250,
    basePrice: 2950,
  },
  {
    symbol: "HDFCBANK",
    name: "HDFC Bank Limited",
    kind: "stock",
    quoteSymbol: "HDFCBANK.NS",
    exchange: "NSE_EQ",
    strikeStep: 20,
    lotSize: 550,
    basePrice: 1690,
  },
  {
    symbol: "ICICIBANK",
    name: "ICICI Bank Limited",
    kind: "stock",
    quoteSymbol: "ICICIBANK.NS",
    exchange: "NSE_EQ",
    strikeStep: 10,
    lotSize: 700,
    basePrice: 1225,
  },
  {
    symbol: "INFY",
    name: "Infosys Limited",
    kind: "stock",
    quoteSymbol: "INFY.NS",
    exchange: "NSE_EQ",
    strikeStep: 20,
    lotSize: 300,
    basePrice: 1490,
  },
  {
    symbol: "TCS",
    name: "Tata Consultancy Services Limited",
    kind: "stock",
    quoteSymbol: "TCS.NS",
    exchange: "NSE_EQ",
    strikeStep: 50,
    lotSize: 175,
    basePrice: 3900,
  },
  {
    symbol: "AXISBANK",
    name: "Axis Bank Limited",
    kind: "stock",
    quoteSymbol: "AXISBANK.NS",
    exchange: "NSE_EQ",
    strikeStep: 10,
    lotSize: 625,
    basePrice: 1170,
  },
  {
    symbol: "SBIN",
    name: "State Bank of India",
    kind: "stock",
    quoteSymbol: "SBIN.NS",
    exchange: "NSE_EQ",
    strikeStep: 10,
    lotSize: 750,
    basePrice: 840,
  },
  {
    symbol: "BAJFINANCE",
    name: "Bajaj Finance Limited",
    kind: "stock",
    quoteSymbol: "BAJFINANCE.NS",
    exchange: "NSE_EQ",
    strikeStep: 50,
    lotSize: 125,
    basePrice: 7050,
  },
];

export function findUnderlying(symbol?: string) {
  if (!symbol) return OPTION_UNDERLYINGS[0];
  return (
    OPTION_UNDERLYINGS.find(
      (item) => item.symbol.toLowerCase() === symbol.toLowerCase()
    ) ?? OPTION_UNDERLYINGS[0]
  );
}
