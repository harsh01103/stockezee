import fs from "fs";
import path from "path";
import crypto from "crypto";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DATA_DIR = path.join(__dirname, "..", "data");
const LEDGER_FILE = path.join(DATA_DIR, "ledger.json");

// IST timestamp helper — stores all trade times in IST (+05:30)
function istNow() {
  const now = new Date();
  // Format in IST using Intl
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false, fractionalSecondDigits: 3
  }).formatToParts(now);
  const get = (type) => parts.find(p => p.type === type)?.value || '00';
  return `${get('year')}-${get('month')}-${get('day')}T${get('hour')}:${get('minute')}:${get('second')}.${String(now.getMilliseconds()).padStart(3,'0')}+05:30`;
}
export { istNow };

// Ensure data directory exists
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

// Initialize ledger if it doesn't exist
if (!fs.existsSync(LEDGER_FILE)) {
  const defaultLedger = {
    balance: 100000,
    trades: []
  };
  fs.writeFileSync(LEDGER_FILE, JSON.stringify(defaultLedger, null, 2), "utf8");
}

function readLedger() {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const data = fs.readFileSync(LEDGER_FILE, "utf8");
      if (data.trim().length === 0) throw new Error("File empty during concurrent write");
      return JSON.parse(data);
    } catch (err) {
      if (attempt === 2) {
        console.error("Error reading ledger after retries:", err);
        return { balance: 100000, trades: [] };
      }
      // Brief sleep for sync retry
      const end = Date.now() + 50;
      while (Date.now() < end) {}
    }
  }
  return { balance: 100000, trades: [] };
}

function writeLedger(ledger) {
  try {
    const tmpFile = `${LEDGER_FILE}.tmp.${Date.now()}`;
    fs.writeFileSync(tmpFile, JSON.stringify(ledger, null, 2), "utf8");
    fs.renameSync(tmpFile, LEDGER_FILE);
  } catch (err) {
    console.error("Error writing ledger:", err);
  }
}

function calculateCharges(premium, qty, isBuy) {
  const turnover = premium * qty;
  const brokerage = 20; // flat per executed order
  const exchangeCharge = turnover * 0.0003503; // 0.03503% on NSE options
  const stt = !isBuy ? turnover * 0.00125 : 0; // 0.125% on sell side premium
  const sebiCharge = turnover * 0.000001; // ₹10 per crore (0.0001%)
  const stampDuty = isBuy ? turnover * 0.00003 : 0; // 0.003% on buy side
  const gst = (brokerage + exchangeCharge + sebiCharge) * 0.18; // 18% GST

  const total = brokerage + exchangeCharge + stt + sebiCharge + stampDuty + gst;

  return {
    brokerage,
    exchangeCharge,
    stt,
    sebiCharge,
    stampDuty,
    gst,
    total
  };
}

export function getLedgerState() {
  const ledger = readLedger();
  
  let totalPnl = 0;
  let closedCount = 0;
  let latestTradePnl = 0;
  
  for (const t of ledger.trades) {
    if (t.status === "CLOSED" && t.netPnl !== null && t.netPnl !== undefined) {
      totalPnl += t.netPnl;
      closedCount++;
      latestTradePnl = t.netPnl;
    } else if (t.status === "CLOSED" && t.pnl !== null && t.pnl !== undefined) {
      // Backwards compatibility for old trades
      totalPnl += t.pnl;
      closedCount++;
      latestTradePnl = t.pnl;
    }
  }

  const avgProfit = closedCount > 0 ? totalPnl / closedCount : 0;

  return {
    balance: ledger.balance,
    totalPnl,
    avgProfit,
    latestTradePnl,
    trades: ledger.trades.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  };
}

function isMarketOpen() {
  const now = new Date();
  
  // Format the time in IST (Asia/Kolkata)
  const options = { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: false, weekday: 'long' };
  const formatter = new Intl.DateTimeFormat('en-US', options);
  const parts = formatter.formatToParts(now);
  
  let hour = 0, minute = 0, weekday = '';
  for (const p of parts) {
    if (p.type === 'hour') hour = parseInt(p.value, 10);
    if (p.type === 'minute') minute = parseInt(p.value, 10);
    if (p.type === 'weekday') weekday = p.value;
  }
  
  if (weekday === 'Saturday' || weekday === 'Sunday') {
    return false;
  }
  
  const timeInMinutes = hour * 60 + minute;
  const marketOpen = 9 * 60 + 15; // 09:15 AM
  const marketClose = 15 * 60 + 30; // 03:30 PM
  
  return timeInMinutes >= marketOpen && timeInMinutes <= marketClose;
}

export function openTrade(tradeData) {
  if (!isMarketOpen()) {
    throw new Error("Market is currently closed. Trading is only allowed between 09:15 AM and 03:30 PM IST on weekdays.");
  }

  const ledger = readLedger();
  
  const isBuy = tradeData.action.startsWith("BUY");
  const entryCharges = calculateCharges(tradeData.entryPrice, tradeData.qty, isBuy);
  
  // Count concurrent open positions at this moment
  const concurrentOpenPositions = ledger.trades.filter(t => t.status === "OPEN").length;
  
  const newTrade = {
    id: crypto.randomUUID(),
    contractSymbol: tradeData.contractSymbol,
    underlying: tradeData.underlying,
    expiry: tradeData.expiry,
    strike: tradeData.strike,
    side: tradeData.side,
    action: tradeData.action,
    qty: tradeData.qty,
    lotSize: tradeData.qty, // explicit lot size field
    entryPrice: tradeData.entryPrice,
    entryOrderType: tradeData.notes?.includes("[AUTO-TRADE]") ? "AUTO" : "MANUAL",
    exitPrice: null,
    grossPnl: null,
    netPnl: null,
    returnPercent: null,
    entryCharges,
    exitCharges: null,
    endingBalance: null,
    capitalDeployed: tradeData.entryPrice * tradeData.qty,
    concurrentPositions: concurrentOpenPositions + 1,
    status: "OPEN",
    timestamp: istNow(),
    exitTimestamp: null,
    notes: tradeData.notes || "",
    metadata: tradeData.metadata || {},
    mfe: null,
    mae: null,
    holdingDuration: null,
    rMultiple: null,
    exitReason: null,
    exitSlippage: null
  };
  
  ledger.balance -= entryCharges.total;
  ledger.trades.push(newTrade);
  writeLedger(ledger);
  
  return getLedgerState();
}

export function closeTrade(tradeId, exitPrice, exitMetrics = {}) {
  if (!isMarketOpen() && exitMetrics.exitReason !== "Expiry Auto-Squareoff") {
    throw new Error("Market is currently closed. Trading is only allowed between 09:15 AM and 03:30 PM IST on weekdays.");
  }

  const ledger = readLedger();
  
  const trade = ledger.trades.find(t => t.id === tradeId);
  if (!trade) {
    throw new Error("Trade not found");
  }
  if (trade.status === "CLOSED") {
    throw new Error("Trade already closed");
  }

  trade.exitPrice = exitPrice;
  trade.exitReason = exitMetrics.exitReason || "Manual Close";
  trade.mfe = exitMetrics.mfe || null;
  trade.mae = exitMetrics.mae || null;
  trade.peakPrice = exitMetrics.peakPrice || null;
  trade.troughPrice = exitMetrics.troughPrice || null;
  trade.holdingDuration = exitMetrics.holdingDuration || null;
  trade.rMultiple = exitMetrics.rMultiple || null;
  
  const entryDate = new Date(trade.timestamp).toDateString();
  const exitDate = new Date().toDateString();
  trade.holdingMode = entryDate === exitDate ? "intraday" : "overnight";
  
  const isBuy = trade.action.startsWith("BUY");
  const isClosingBuy = !isBuy;
  const exitCharges = calculateCharges(exitPrice, trade.qty, isClosingBuy);
  
  trade.exitCharges = exitCharges;
  
  if (isBuy) {
    trade.grossPnl = (trade.exitPrice - trade.entryPrice) * trade.qty;
  } else {
    trade.grossPnl = (trade.entryPrice - trade.exitPrice) * trade.qty;
  }
  
  // For backwards compatibility
  trade.pnl = trade.grossPnl;
  
  // Calculate net PnL (gross - entry charges - exit charges)
  const entryTotal = trade.entryCharges ? trade.entryCharges.total : 0;
  trade.netPnl = trade.grossPnl - entryTotal - exitCharges.total;
  
  // Return percentage
  const capitalDeployed = trade.entryPrice * trade.qty;
  trade.returnPercent = capitalDeployed > 0 ? parseFloat(((trade.netPnl / capitalDeployed) * 100).toFixed(4)) : 0;
  
  // Exit slippage (vs target or SL)
  if (trade.metadata) {
    if (trade.exitReason === "Hit Target 1" && trade.metadata.target1) {
      trade.exitSlippage = parseFloat((exitPrice - trade.metadata.target1).toFixed(2));
    } else if (trade.exitReason === "Hit Target 2" && trade.metadata.target2) {
      trade.exitSlippage = parseFloat((exitPrice - trade.metadata.target2).toFixed(2));
    } else if (trade.exitReason === "Hit Stop Loss" && trade.metadata.stopLoss) {
      trade.exitSlippage = parseFloat((exitPrice - trade.metadata.stopLoss).toFixed(2));
    }
  }
  
  trade.status = "CLOSED";
  trade.exitTimestamp = istNow();
  
  // Apply gross PnL and deduct exit charges from permanent balance
  ledger.balance += trade.grossPnl;
  ledger.balance -= exitCharges.total;
  
  trade.endingBalance = ledger.balance;
  
  writeLedger(ledger);
  
  return getLedgerState();
}

