import axios from "axios";
import YahooFinance from "yahoo-finance2";
const yahooFinance = new YahooFinance();

const INDEX_UNDERLYINGS = [
  {
    symbol: "NIFTY",
    name: "NIFTY 50",
    kind: "index",
    exchange: "NSE_INDEX",
    instrument_key: "NSE_INDEX|Nifty 50",
    strikeStep: 50,
    lotSize: 65,
  },
  {
    symbol: "BANKNIFTY",
    name: "NIFTY BANK",
    kind: "index",
    exchange: "NSE_INDEX",
    instrument_key: "NSE_INDEX|Nifty Bank",
    strikeStep: 100,
    lotSize: 30,
  },
  {
    symbol: "FINNIFTY",
    name: "NIFTY FIN SERVICE",
    kind: "index",
    exchange: "NSE_INDEX",
    instrument_key: "NSE_INDEX|Nifty Fin Service",
    strikeStep: 50,
    lotSize: 60,
  },
  {
    symbol: "CRUDEOIL",
    name: "MCX Crude Oil",
    kind: "commodity",
    exchange: "MCX_FO",
    instrument_key: "COMM|CRUDEOIL",
    strikeStep: 10,
    lotSize: 100,
  },
  {
    symbol: "NATURALGAS",
    name: "MCX Natural Gas",
    kind: "commodity",
    exchange: "MCX_FO",
    instrument_key: "COMM|NATURALGAS",
    strikeStep: 5,
    lotSize: 1250,
  },
  {
    symbol: "GOLD",
    name: "MCX Gold",
    kind: "commodity",
    exchange: "MCX_FO",
    instrument_key: "COMM|GOLD",
    strikeStep: 100,
    lotSize: 1,
  },
  {
    symbol: "SILVER",
    name: "MCX Silver",
    kind: "commodity",
    exchange: "MCX_FO",
    instrument_key: "COMM|SILVER",
    strikeStep: 500,
    lotSize: 30,
  },
];

function getMarketStatus(now = new Date()) {
  const ist = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
  const day = ist.getDay();
  const minutes = ist.getHours() * 60 + ist.getMinutes();
  if (day === 0 || day === 6) return "closed";
  if (minutes >= 540 && minutes < 555) return "pre-open";
  if (minutes >= 555 && minutes <= 930) return "open";
  if (minutes > 930 && minutes <= 960) return "after-hours";
  return "closed";
}

function getEffectiveToken(runtimeAccessToken) {
  return process.env.DHAN_ACCESS_TOKEN || runtimeAccessToken || process.env.UPSTOX_ACCESS_TOKEN || null;
}

const requestCache = new Map();

async function upstoxGet(path, runtimeAccessToken) {
  const token = getEffectiveToken(runtimeAccessToken);
  if (!token) {
    const err = new Error('Upstox authentication required. Login via /auth/upstox or provide UPSTOX_ACCESS_TOKEN.');
    err.status = 401;
    throw err;
  }
  
  const cacheKey = path;
  const now = Date.now();
  if (requestCache.has(cacheKey)) {
    const cached = requestCache.get(cacheKey);
    if (now - cached.time < 3000) return cached.promise;
  }

  const promise = (async () => {
    try {
      const response = await axios.get(`https://api.upstox.com${path}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'application/json'
        }
      });
      return response.data;
    } catch (error) {
      if (error.response?.status === 401 || error.response?.status === 403) {
        const err = new Error('Upstox authentication required or expired. Login again.');
        err.status = error.response?.status;
        throw err;
      }
      const err = new Error(error.response?.data?.errors?.[0]?.message || error.message);
      err.status = error.response?.status || 500;
      throw err;
    }
  })();

  requestCache.set(cacheKey, { time: now, promise });
  return promise;
}

function pickStep(price) {
  if (price >= 50000) return 100;
  if (price >= 10000) return 50;
  if (price >= 2000) return 20;
  return 10;
}

function normalizeEquity(instrument) {
  return {
    symbol: instrument.symbol,
    name: instrument.name,
    kind: "stock",
    exchange: instrument.exchange,
    instrument_key: instrument.instrument_key,
    strikeStep: pickStep(Number(instrument.last_price || 0)),
    lotSize: 1,
  };
}

export function searchOptionUnderlyings(query, instruments) {
  const trimmed = String(query || "").trim().toLowerCase();
  const stockMatches = instruments
    .filter((instrument) => {
      if (!trimmed) return true;
      return (
        (instrument.symbol || "").toLowerCase().includes(trimmed) ||
        (instrument.name || "").toLowerCase().includes(trimmed)
      );
    })
    .slice(0, 20)
    .map(normalizeEquity);

  const indexMatches = INDEX_UNDERLYINGS.filter((instrument) => {
    if (!trimmed) return true;
    return (
      (instrument.symbol || "").toLowerCase().includes(trimmed) ||
      (instrument.name || "").toLowerCase().includes(trimmed)
    );
  });

  const merged = [...indexMatches, ...stockMatches];
  const deduped = [];
  const seen = new Set();
  for (const item of merged) {
    if (seen.has(item.symbol)) continue;
    seen.add(item.symbol);
    deduped.push(item);
  }
  return deduped.slice(0, 24);
}

export function resolveUnderlying(symbol, instruments) {
  const normalized = String(symbol || "").trim().toUpperCase();
  const index = INDEX_UNDERLYINGS.find((item) => item.symbol === normalized);
  if (index) return index;
  const equity = instruments.find((item) => item.symbol.toUpperCase() === normalized);
  if (!equity) {
    const error = new Error(`Unsupported underlying: ${symbol}`);
    error.status = 404;
    throw error;
  }
  return normalizeEquity(equity);
}

function extractQuotePayload(payload, instrumentKey) {
  const data = payload?.data || payload;
  if (!data) return null;
  if (data[instrumentKey]) return data[instrumentKey];
  const values = Object.values(data);
  return values.length > 0 ? values[0] : null;
}

function toDashboardQuote(rawQuote, symbol, name) {
  const ohlc = rawQuote?.ohlc || {};
  const lastPrice = Number(rawQuote?.last_price ?? rawQuote?.ltp ?? ohlc.close ?? 0);
  
  let change = 0;
  let previousClose = lastPrice;

  if (rawQuote?.net_change !== undefined && rawQuote?.net_change !== null) {
      change = Number(rawQuote.net_change);
      previousClose = lastPrice - change;
  } else {
      previousClose = Number(rawQuote?.close_price ?? rawQuote?.prev_close ?? ohlc.close ?? lastPrice);
      change = lastPrice - previousClose;
  }

  return {
    symbol,
    name,
    price: lastPrice,
    previousClose,
    change,
    changePercent: previousClose ? (change / previousClose) * 100 : 0,
    dayHigh: Number(ohlc.high ?? lastPrice),
    dayLow: Number(ohlc.low ?? lastPrice),
    volume: Number(rawQuote?.volume ?? rawQuote?.vol ?? 0),
    marketStatus: getMarketStatus(),
    timestamp: new Date().toISOString(),
  };
}

function roundToStep(value, step) {
  return Math.round(value / step) * step;
}

function getExpiryList(contracts) {
  return [...new Set(contracts.map((item) => item.expiry || item.expiry_date || item).filter(Boolean))].sort();
}

function getMoneyness(optionType, strike, spot, atmStrike) {
  if (strike === atmStrike) return "ATM";
  if (optionType === "CE") return strike < spot ? "ITM" : "OTM";
  return strike > spot ? "ITM" : "OTM";
}

function upstoxToChainRow(data, spotPrice, atmStrike) {
  const strike = Number(data.strike_price);
  const call = data.call_options?.market_data || {};
  const put = data.put_options?.market_data || {};
  const callGreeks = data.call_options?.option_greeks || {};
  const putGreeks = data.put_options?.option_greeks || {};
  
  return {
    strike,
    call: {
      contractSymbol: data.call_options?.instrument_key || "",
      strike,
      type: "CE",
      change: 0,
      changePercent: 0,
      ltp: Number(call.ltp || 0),
      volume: Number(call.volume || 0),
      oi: Number(call.oi || 0),
      oiChange: 0,
      bid: Number(call.bid_price || 0),
      ask: Number(call.ask_price || 0),
      iv: Number(callGreeks.iv || 0) * 100,
      delta: Number(callGreeks.delta || 0),
      theta: Number(callGreeks.theta || 0),
      gamma: Number(callGreeks.gamma || 0),
      vega: Number(callGreeks.vega || 0),
      spread: 0,
      moneyness: strike < spotPrice ? "ITM" : strike === atmStrike ? "ATM" : "OTM",
    },
    put: {
      contractSymbol: data.put_options?.instrument_key || "",
      strike,
      type: "PE",
      change: 0,
      changePercent: 0,
      ltp: Number(put.ltp || 0),
      volume: Number(put.volume || 0),
      oi: Number(put.oi || 0),
      oiChange: 0,
      bid: Number(put.bid_price || 0),
      ask: Number(put.ask_price || 0),
      iv: Number(putGreeks.iv || 0) * 100,
      delta: Number(putGreeks.delta || 0),
      theta: Number(putGreeks.theta || 0),
      gamma: Number(putGreeks.gamma || 0),
      vega: Number(putGreeks.vega || 0),
      spread: 0,
      moneyness: strike > spotPrice ? "ITM" : strike === atmStrike ? "ATM" : "OTM",
    },
    isAtm: strike === atmStrike,
  };
}

function generateCommodityChain(spot, atmStrike, step, isLtpOnly = false) {
  const strikes = [];
  for (let i = -15; i <= 15; i++) strikes.push(atmStrike + i * step);
  return strikes.map((strike) => {
    const dist = Math.abs(strike - spot);
    const basePremium = Math.max(1, (spot * 0.02) - (dist * 0.3));
    // Add stable jitter based on strike
    const callPremium = Number((basePremium + (strike % 5) * 0.5).toFixed(2));
    const putPremium = Number((basePremium + ((strike + 1) % 5) * 0.5).toFixed(2));

    if (isLtpOnly) {
      return {
        strike,
        callLtp: callPremium,
        callBid: Number((callPremium - 0.5).toFixed(2)),
        callAsk: Number((callPremium + 0.5).toFixed(2)),
        callClosePrice: callPremium,
        putLtp: putPremium,
        putBid: Number((putPremium - 0.5).toFixed(2)),
        putAsk: Number((putPremium + 0.5).toFixed(2)),
        putClosePrice: putPremium,
      };
    }

    return {
      strike,
      call: {
        contractSymbol: `CE-${strike}`,
        type: "CE",
        strike,
        ltp: callPremium,
        change: 0,
        changePercent: 0,
        volume: Math.floor(1000 + (Math.random() * 5000)),
        oi: Math.floor(5000 + (Math.random() * 10000)),
        oiChange: 0,
        bid: Number((callPremium - 0.5).toFixed(2)),
        ask: Number((callPremium + 0.5).toFixed(2)),
        iv: Number((20 + (Math.random() * 10)).toFixed(1)),
        spread: 1.0,
        moneyness: getMoneyness("CE", strike, spot, atmStrike),
      },
      put: {
        contractSymbol: `PE-${strike}`,
        type: "PE",
        strike,
        ltp: putPremium,
        change: 0,
        changePercent: 0,
        volume: Math.floor(1000 + (Math.random() * 5000)),
        oi: Math.floor(5000 + (Math.random() * 10000)),
        oiChange: 0,
        bid: Number((putPremium - 0.5).toFixed(2)),
        ask: Number((putPremium + 0.5).toFixed(2)),
        iv: Number((20 + (Math.random() * 10)).toFixed(1)),
        spread: 1.0,
        moneyness: getMoneyness("PE", strike, spot, atmStrike),
      },
      isAtm: strike === atmStrike,
    };
  });
}

export async function getOptionsDashboard(symbol, instruments, runtimeAccessToken) {
  const underlying = resolveUnderlying(symbol, instruments);
  
  let expiries = [];
  if (underlying.kind !== "commodity") {
    const contractPayload = await upstoxGet(`/v2/option/contract?instrument_key=${encodeURIComponent(underlying.instrument_key)}`, runtimeAccessToken);
    if (contractPayload?.data) {
      expiries = getExpiryList(contractPayload.data);
    }
  }
  
  const expiry = expiries[0] || "";
  
  // We need to fetch the option chain for the first expiry to get the spot price (last_price)
  let quoteObj = null;
  if (underlying.kind !== "commodity" && expiry) {
    const quotePayload = await upstoxGet(`/v2/market-quote/quotes?instrument_key=${encodeURIComponent(underlying.instrument_key)}`, runtimeAccessToken);
    const quoteData = extractQuotePayload(quotePayload, underlying.instrument_key);
    quoteObj = toDashboardQuote(quoteData, underlying.symbol, underlying.name);
  } 
  
  if (!quoteObj) {
    // fallback for non-dhan (commodity)
    try {
      const q = await yahooFinance.quote(underlying.yahoo_ticker);
      quoteObj = {
        symbol: underlying.symbol,
        name: underlying.name,
        price: q.regularMarketPrice,
        previousClose: q.regularMarketPreviousClose,
        change: q.regularMarketChange,
        changePercent: q.regularMarketChangePercent,
        dayHigh: q.regularMarketDayHigh || q.regularMarketPrice,
        dayLow: q.regularMarketDayLow || q.regularMarketPrice,
        volume: q.regularMarketVolume || 0,
        marketStatus: getMarketStatus(),
        timestamp: new Date().toISOString()
      };
    } catch (e) {
      console.error("VIX/Fallback quote fetch error", e);
      quoteObj = { price: 0, change: 0, changePercent: 0, dayHigh: 0, dayLow: 0, volume: 0, previousClose: 0, marketStatus: getMarketStatus(), timestamp: new Date().toISOString() };
    }
  }

  const step = pickStep(quoteObj.price);
  const atmStrike = Math.round(quoteObj.price / step) * step;

  let vix = null;
  try {
    const vixQ = await yahooFinance.quote("^INDIAVIX");
    vix = Number(vixQ.regularMarketPrice).toFixed(2);
  } catch (e) {}

  return {
    underlying: {
      ...underlying,
      strikeStep: step,
      lotSize: underlying.lotSize || 1, // Will update lot size when building rows if possible
    },
    quote: quoteObj,
    vix,
    expiries,
    expiry,
    atmStrike,
    strikeStep: step,
    generatedAt: new Date().toISOString(),
    meta: {
      source: underlying.kind !== "commodity" ? "upstox" : "generated-research",
      ivAvailable: true,
      cacheHit: false,
    },
  };
}

export async function getOptionChain(symbol, expiry, instruments, runtimeAccessToken) {
  const dashboard = await getOptionsDashboard(symbol, instruments, runtimeAccessToken);
  const selectedExpiry = expiry || dashboard.expiry;

  if (dashboard.meta.source === "generated-research") {
    return {
      ...dashboard,
      expiry: selectedExpiry,
      rows: generateCommodityChain(dashboard.quote.price, dashboard.atmStrike, dashboard.strikeStep, false),
      generatedAt: new Date().toISOString(),
    };
  }

  let rows = [];
  const chainPayload = await upstoxGet(`/v2/option/chain?instrument_key=${encodeURIComponent(dashboard.underlying.instrument_key)}&expiry_date=${selectedExpiry}`, runtimeAccessToken);
  const dataArr = chainPayload?.data || [];
  rows = dataArr
    .map((data) => upstoxToChainRow(data, dashboard.quote.price, dashboard.atmStrike))
    .sort((left, right) => left.strike - right.strike);

  return {
    ...dashboard,
    expiry: selectedExpiry,
    rows,
    generatedAt: new Date().toISOString(),
  };
}

// Lightweight LTP-only chain fetch — skips full dashboard overhead
const ltpCache = { instrumentKey: null, expiry: null };

export async function getOptionChainLtp(symbol, expiry, instruments, runtimeAccessToken) {
  const underlying = resolveUnderlying(symbol, instruments);
  
  if (underlying.kind === "commodity") {
    const dashboard = await getOptionsDashboard(symbol, instruments, runtimeAccessToken);
    return { 
      rows: generateCommodityChain(dashboard.quote.price, dashboard.atmStrike, dashboard.strikeStep, true), 
      generatedAt: new Date().toISOString() 
    };
  }

  let selectedExpiry = expiry;
  if (!selectedExpiry) {
    const contractPayload = await upstoxGet(`/v2/option/contract?instrument_key=${encodeURIComponent(underlying.instrument_key)}`, runtimeAccessToken);
    const expiries = getExpiryList(contractPayload?.data || []);
    selectedExpiry = expiries[0] || "";
  }

  let rows = [];
  const chainPayload = await upstoxGet(`/v2/option/chain?instrument_key=${encodeURIComponent(underlying.instrument_key)}&expiry_date=${selectedExpiry}`, runtimeAccessToken);
  const dataArr = chainPayload?.data || [];
  rows = dataArr.map((data) => {
    const call = data.call_options?.market_data || {};
    const put = data.put_options?.market_data || {};
    const strike = Number(data.strike_price);
    return {
      strike,
      callLtp: Number(call.ltp || 0),
      callBid: Number(call.bid_price || 0),
      callAsk: Number(call.ask_price || 0),
      callClosePrice: Number(call.close_price || 0),
      putLtp: Number(put.ltp || 0),
      putBid: Number(put.bid_price || 0),
      putAsk: Number(put.ask_price || 0),
      putClosePrice: Number(put.close_price || 0),
    };
  }).sort((left, right) => left.strike - right.strike);

  return { rows, generatedAt: new Date().toISOString() };
}

export function buildAnalytics(rows) {
  if (!rows.length) {
    return {
      pcr: { value: "0.00", confidence: "low" },
      maxPain: { value: "-", confidence: "low" },
      largestCallOi: { value: "-", confidence: "low" },
      largestPutOi: { value: "-", confidence: "low" },
      highestOiChange: { value: "-", confidence: "low" },
      ivSummary: { value: "-", confidence: "low" },
      supportEstimate: { value: "-", confidence: "low" },
      resistanceEstimate: { value: "-", confidence: "low" },
    };
  }

  const totalCallOi = rows.reduce((sum, row) => sum + row.call.oi, 0);
  const totalPutOi = rows.reduce((sum, row) => sum + row.put.oi, 0);
  const pcr = totalCallOi ? totalPutOi / totalCallOi : 0;
  const largestCall = rows.reduce((best, row) => (row.call.oi > best.call.oi ? row : best), rows[0]);
  const largestPut = rows.reduce((best, row) => (row.put.oi > best.put.oi ? row : best), rows[0]);
  const biggestShift = rows.reduce((best, row) => {
    const currentMax = Math.max(Math.abs(best.call.oiChange), Math.abs(best.put.oiChange));
    const nextMax = Math.max(Math.abs(row.call.oiChange), Math.abs(row.put.oiChange));
    return nextMax > currentMax ? row : best;
  }, rows[0]);
  const ivs = rows.flatMap((row) => [row.call.iv, row.put.iv]).filter((value) => value != null);
  const avgIv = ivs.length ? ivs.reduce((sum, value) => sum + Number(value), 0) / ivs.length : 0;
  const confidence = (value) => (value > 0.7 ? "high" : value > 0.4 ? "medium" : "low");

  return {
    pcr: { value: pcr.toFixed(2), confidence: confidence(1 - Math.min(Math.abs(1 - pcr), 1)) },
    maxPain: { value: `${rows[Math.floor(rows.length / 2)].strike}`, confidence: "medium" },
    largestCallOi: { value: `${largestCall.strike} (${largestCall.call.oi.toLocaleString("en-IN")})`, confidence: confidence(largestCall.call.oi / Math.max(totalCallOi, 1)) },
    largestPutOi: { value: `${largestPut.strike} (${largestPut.put.oi.toLocaleString("en-IN")})`, confidence: confidence(largestPut.put.oi / Math.max(totalPutOi, 1)) },
    highestOiChange: {
      value:
        Math.abs(biggestShift.call.oiChange) >= Math.abs(biggestShift.put.oiChange)
          ? `CE ${biggestShift.strike} (${biggestShift.call.oiChange.toLocaleString("en-IN")})`
          : `PE ${biggestShift.strike} (${biggestShift.put.oiChange.toLocaleString("en-IN")})`,
      confidence: "medium",
    },
    ivSummary: { value: `${avgIv.toFixed(1)} avg IV`, confidence: avgIv > 25 ? "high" : avgIv > 15 ? "medium" : "low" },
    supportEstimate: { value: `${largestPut.strike}`, confidence: "medium" },
    resistanceEstimate: { value: `${largestCall.strike}`, confidence: "medium" },
  };
}

export async function getIntradayChart(symbol, instruments, runtimeAccessToken, { instrumentKey } = {}) {
  const resolvedKey = instrumentKey || resolveUnderlying(symbol, instruments).instrument_key;
  
  if (resolvedKey.startsWith("CE-") || resolvedKey.startsWith("PE-")) {
    const candles = [];
    const now = Date.now();
    let price = 150;
    for (let i = 0; i < 60; i++) {
      const time = now - (60 - i) * 60000;
      price += (Math.random() - 0.5) * 5;
      candles.push({
        time: Math.floor(time / 1000),
        open: price,
        high: price + 2,
        low: price - 2,
        close: price + 1,
        volume: Math.floor(Math.random() * 1000)
      });
    }
    return candles;
  }

  try {
    const payload = await upstoxGet(`/v2/historical-candle/intraday/${encodeURIComponent(resolvedKey)}/1minute`, runtimeAccessToken);
    const candles = payload?.data?.candles || payload?.candles || [];
    return candles
      .map((entry) => ({
        time: Math.floor(new Date(entry[0]).getTime() / 1000),
        open: Number(entry[1]),
        high: Number(entry[2]),
        low: Number(entry[3]),
        close: Number(entry[4]),
        volume: Number(entry[5] ?? 0),
      }))
      .sort((left, right) => left.time - right.time);
  } catch (error) {
    console.warn(`[getIntradayChart] Failed to fetch chart for ${resolvedKey}. Returning synthetic flatline. Error: ${error.message}`);
    // Return a synthetic flatline chart so the UI doesn't break for illiquid options
    const candles = [];
    const now = Date.now();
    let price = 100;
    for (let i = 0; i < 60; i++) {
      const time = now - (60 - i) * 60000;
      candles.push({
        time: Math.floor(time / 1000),
        open: price,
        high: price + 0.1,
        low: price - 0.1,
        close: price,
        volume: 0
      });
    }
    return candles;
  }
}
