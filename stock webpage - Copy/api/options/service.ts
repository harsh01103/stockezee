import { getUnderlyingQuote } from "../market-data/service";
import { findUnderlying } from "./catalog";
import type { OptionChainResponse, OptionChainRow, OptionLeg } from "./types";
import { clamp, getUpcomingExpiries, roundToStep, seededUnit } from "./utils";

const chainCache = new Map<string, { expiresAt: number; value: OptionChainResponse }>();

function getTimeToExpiry(expiry: string) {
  const expiryTime = new Date(`${expiry}T15:30:00+05:30`).getTime();
  const diff = Math.max(expiryTime - Date.now(), 1);
  return diff / (1000 * 60 * 60 * 24);
}

function buildLeg(params: {
  symbol: string;
  type: "CE" | "PE";
  strike: number;
  spot: number;
  expiry: string;
  step: number;
}) {
  const { symbol, type, strike, spot, expiry, step } = params;
  const timeToExpiry = getTimeToExpiry(expiry);
  const intrinsic =
    type === "CE" ? Math.max(spot - strike, 0) : Math.max(strike - spot, 0);
  const distance = Math.abs(spot - strike) / step;
  const timeValue = Math.max(4, spot * 0.0025 * Math.exp(-distance / 3)) * (1 + timeToExpiry / 35);
  const baseLtp = intrinsic + timeValue;
  const spreadFactor = 0.004 + distance * 0.0004 + seededUnit(`${symbol}:${expiry}:${strike}:${type}:spread`) * 0.004;
  const spread = Math.max(0.05, baseLtp * spreadFactor);
  const volumeBase = Math.max(
    120,
    Math.round((25000 / (distance + 1)) * (0.6 + seededUnit(`${symbol}:${expiry}:${strike}:${type}:vol`)))
  );
  const oiBase = Math.max(
    500,
    Math.round((90000 / (distance + 1.2)) * (0.8 + seededUnit(`${symbol}:${expiry}:${strike}:${type}:oi`)))
  );
  const oiChange = Math.round(oiBase * ((seededUnit(`${symbol}:${expiry}:${strike}:${type}:oic`) - 0.48) * 0.18));
  const previousClose = baseLtp * (0.985 + seededUnit(`${symbol}:${expiry}:${strike}:${type}:prev`) * 0.03);
  const change = baseLtp - previousClose;
  const changePercent = previousClose ? (change / previousClose) * 100 : 0;
  const iv = clamp(12 + distance * 1.4 + timeToExpiry * 0.22 + seededUnit(`${symbol}:${expiry}:${strike}:${type}:iv`) * 6, 8, 42);

  const moneyness =
    Math.abs(strike - spot) < step / 2
      ? "ATM"
      : type === "CE"
        ? strike < spot
          ? "ITM"
          : "OTM"
        : strike > spot
          ? "ITM"
          : "OTM";

  const leg: OptionLeg = {
    contractSymbol: `${symbol}-${expiry}-${strike}-${type}`,
    strike,
    type,
    ltp: Number(baseLtp.toFixed(2)),
    change: Number(change.toFixed(2)),
    changePercent: Number(changePercent.toFixed(2)),
    volume: volumeBase,
    oi: oiBase,
    oiChange,
    bid: Number(Math.max(0.05, baseLtp - spread / 2).toFixed(2)),
    ask: Number((baseLtp + spread / 2).toFixed(2)),
    iv: Number(iv.toFixed(2)),
    spread: Number(spread.toFixed(2)),
    moneyness,
  };

  return leg;
}

export async function getOptionChain(args: {
  symbol?: string;
  expiry?: string;
  strikes?: number;
}) {
  const underlying = findUnderlying(args.symbol);
  const expiries = getUpcomingExpiries();
  const expiry = expiries.includes(args.expiry ?? "") ? (args.expiry as string) : expiries[0];
  const cacheKey = `${underlying.symbol}:${expiry}:${args.strikes ?? 31}`;
  const cached = chainCache.get(cacheKey);

  if (cached && cached.expiresAt > Date.now()) {
    return {
      ...cached.value,
      meta: { ...cached.value.meta, cacheHit: true },
    };
  }

  const quote = await getUnderlyingQuote(underlying);
  const atmStrike = roundToStep(quote.price, underlying.strikeStep);
  const totalRows = clamp(args.strikes ?? 31, 11, 61);
  const half = Math.floor(totalRows / 2);
  const rows: OptionChainRow[] = [];

  for (let index = -half; index <= half; index += 1) {
    const strike = atmStrike + index * underlying.strikeStep;
    const call = buildLeg({
      symbol: underlying.symbol,
      type: "CE",
      strike,
      spot: quote.price,
      expiry,
      step: underlying.strikeStep,
    });
    const put = buildLeg({
      symbol: underlying.symbol,
      type: "PE",
      strike,
      spot: quote.price,
      expiry,
      step: underlying.strikeStep,
    });

    rows.push({
      strike,
      call,
      put,
      isAtm: strike === atmStrike,
    });
  }

  const response: OptionChainResponse = {
    underlying,
    quote,
    expiries,
    expiry,
    atmStrike,
    strikeStep: underlying.strikeStep,
    rows,
    generatedAt: new Date().toISOString(),
    meta: {
      source: "generated-research",
      ivAvailable: true,
      cacheHit: false,
    },
  };

  chainCache.set(cacheKey, { expiresAt: Date.now() + 20_000, value: response });
  return response;
}
