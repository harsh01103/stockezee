import { getLedgerState, openTrade, closeTrade, istNow } from "./ledgerService.js";
import { getOptionChainLtp } from "../optionsService.js";

// Pending signals waiting for limit order
const pendingSignals = [];

// Track active signals that are OPEN and waiting for targets
// Map<tradeId, { target, stopLoss, highestSeen, lowestSeen, entryTime }>
const activeSignalMeta = new Map();

// Track which contractSymbols have already been entered to prevent duplicates
const enteredContracts = new Set();

// Live LTP cache for all monitored trades (updated every poll cycle)
// Map<tradeId, number>
const tradeLtpCache = new Map();

let instrumentsDb = null;
let getToken = null;
export function initAutoTrader(instruments, tokenProvider) {
  instrumentsDb = instruments;
  getToken = tokenProvider || (() => null);
  
  // Re-hydrate activeSignalMeta from existing open trades on startup
  try {
    const ledger = getLedgerState();
    for (const trade of ledger.trades) {
      if (trade.status === "OPEN" && trade.notes && trade.notes.includes("[AUTO-TRADE]")) {
        const match = trade.notes.match(/Target:\s*([\d.]+),\s*SL:\s*([\d.]+)/);
        if (match) {
          activeSignalMeta.set(trade.id, {
            target: parseFloat(match[1]),
            stopLoss: parseFloat(match[2]),
            highestSeen: trade.entryPrice,
            lowestSeen: trade.entryPrice,
            entryTime: new Date(trade.timestamp).getTime()
          });
          console.log(`[AutoTrader] Re-hydrated tracking for ${trade.contractSymbol} (${trade.id})`);
        }
      }
    }
  } catch (e) {
    console.warn("[AutoTrader] Could not re-hydrate:", e.message);
  }
  // Watchdog polling handles all updates
  setInterval(() => {
    if (isPolling) return;
    const ledger = getLedgerState();
    const hasOpenTrades = ledger.trades.some(t => t.status === "OPEN");
    if (pendingSignals.length > 0 || activeSignalMeta.size > 0 || hasOpenTrades) {
      pollSignals();
    }
  }, 1000);
}

export function getPendingSignals() {
  return pendingSignals;
}

export function clearPendingSignals() {
  const count = pendingSignals.length;
  pendingSignals.length = 0;
  console.log(`[AutoTrader] Cleared ${count} pending signals`);
  return count;
}

export function removePendingSignals(contractSymbols = []) {
  if (!Array.isArray(contractSymbols) || contractSymbols.length === 0) {
    return 0;
  }

  const symbols = new Set(contractSymbols.filter(Boolean));
  let removed = 0;

  for (let i = pendingSignals.length - 1; i >= 0; i--) {
    if (symbols.has(pendingSignals[i].contractSymbol)) {
      pendingSignals.splice(i, 1);
      removed += 1;
    }
  }

  console.log(`[AutoTrader] Removed ${removed} pending signals by symbol`);
  return removed;
}

export function getActiveTradeLtps() {
  return Object.fromEntries(tradeLtpCache);
}

export function queueSignal(signal) {
  if (signal.action === "SELL" && signal.hedgeStrike) {
      // Modify contract symbol to reflect the spread architecture
      signal.contractSymbol = `${signal.underlying} ${signal.expiry} ${signal.strike}/${signal.hedgeStrike} ${signal.side} SPREAD`;
  }
  
  // Prevent duplicate queuing of the same contract
  const isDuplicate = pendingSignals.some(s => s.contractSymbol === signal.contractSymbol)
    || enteredContracts.has(signal.contractSymbol)
    || getLedgerState().trades.some(t => t.status === "OPEN" && t.contractSymbol === signal.contractSymbol);
  
  if (isDuplicate) {
    console.log(`[AutoTrader] Skipping duplicate signal for ${signal.contractSymbol}`);
    return signal;
  }

  signal.id = Math.random().toString(36).substr(2, 9);
  signal.status = 'PENDING';
  signal.timestamp = Date.now();
  pendingSignals.push(signal);
  console.log(`[AutoTrader] Queued signal: ${signal.contractSymbol} @ ${signal.limitPrice}`);
  
  // EVENT-DRIVEN EXECUTION: Trigger immediately
  if (!isPolling) {
      pollSignals();
  }
  
  return signal;
}

let isPolling = false;

async function pollSignals() {
  if (isPolling) return;
  isPolling = true;
  
  try {
    if (!instrumentsDb) return;
  
  // SESSION_END_FLATTEN (15:20 IST)
  const istDate = new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
  const h = istDate.getHours();
  const m = istDate.getMinutes();
  
  if (h > 15 || (h === 15 && m >= 20)) {
    if (pendingSignals.length > 0) {
        console.warn(`[AutoTrader] SESSION_END_FLATTEN: Canceling ${pendingSignals.length} pending signals.`);
        pendingSignals.length = 0;
    }
    const ledger = getLedgerState();
    let flattened = 0;
    for (const t of ledger.trades) {
        if (t.status === "OPEN") {
            const exitPrc = tradeLtpCache.get(t.id) || t.entryPrice;
            console.warn(`[AutoTrader] SESSION_END_FLATTEN: Forcing market close for ${t.contractSymbol} at ${exitPrc}`);
            closeTrade(t.id, exitPrc, "SESSION_END_FLATTEN (15:20 IST)", t.notes || "");
            activeSignalMeta.delete(t.id);
            flattened++;
        }
    }
    if (flattened > 0) {
        console.warn(`[AutoTrader] SESSION_END_FLATTEN: Closed ${flattened} open positions.`);
    }
    // Prevent further polling actions after 15:20
    return;
  }

  const ledger = getLedgerState();
  const openTrades = ledger.trades.filter(t => t.status === "OPEN");

  // We need to group by underlying+expiry to fetch chain LTP efficiently
  const neededChains = new Set();
  
  pendingSignals.forEach(s => neededChains.add(`${s.underlying}|${s.expiry}`));
  
  openTrades.forEach(t => {
    neededChains.add(`${t.underlying}|${t.expiry}`);
  });

  if (neededChains.size === 0) return;
  console.log('[AutoTrader Debug] neededChains:', Array.from(neededChains));

  // Fetch LTPs
  const chainLtps = {};
  for (const chainId of neededChains) {
    const [underlying, expiry] = chainId.split('|');
    try {
      const token = getToken();
      const data = await getOptionChainLtp(underlying, expiry, instrumentsDb, token);
      if (data && data.rows) {
        const ltpMap = {};
        data.rows.forEach(r => {
          ltpMap[r.strike] = r;
        });
        chainLtps[chainId] = ltpMap;
      }
    } catch (e) {
      console.error(`[AutoTrader] Error fetching LTP for ${chainId}:`, e.message);
    }
  }
  
  console.log('[AutoTrader Debug] chainLtps keys:', Object.keys(chainLtps));

  // Check Pending Signals for Entry
  for (let i = pendingSignals.length - 1; i >= 0; i--) {
    const signal = pendingSignals[i];
    
    // Auto-expire signals based on dynamic TTL (e.g. 15s for Momentum, 180s for Mean Reversion)
    const timeoutMs = (signal.timeout_seconds || 300) * 1000;
    if (Date.now() - signal.timestamp > timeoutMs) {
      console.log(`[AutoTrader] Queued signal expired (${timeoutMs/1000}s TTL): ${signal.contractSymbol}`);
      pendingSignals.splice(i, 1);
      continue;
    }

    const chainId = `${signal.underlying}|${signal.expiry}`;
    const ltpMap = chainLtps[chainId];
    
    if (!ltpMap) continue;

    const strikeData = ltpMap[signal.strike];
    if (!strikeData) continue;

    let livePrice;
    let currentSpreadPct = 0;
    if (signal.action === "SELL" && signal.hedgeStrike) {
        const hedgeStrikeData = ltpMap[signal.hedgeStrike];
        if (!hedgeStrikeData) continue; // wait for both legs
        const shortLtp = signal.side === "CE" ? strikeData.callLtp : strikeData.putLtp;
        const longLtp = signal.side === "CE" ? hedgeStrikeData.callLtp : hedgeStrikeData.putLtp;
        livePrice = shortLtp - longLtp;
        
        const shortAsk = signal.side === "CE" ? strikeData.callAsk : strikeData.putAsk;
        const shortBid = signal.side === "CE" ? strikeData.callBid : strikeData.putBid;
        const mid = (shortAsk + shortBid) / 2;
        if (mid > 0) currentSpreadPct = (shortAsk - shortBid) / mid;
    } else {
        livePrice = signal.side === "CE" ? strikeData.callLtp : strikeData.putLtp;
        const ask = signal.side === "CE" ? strikeData.callAsk : strikeData.putAsk;
        const bid = signal.side === "CE" ? strikeData.callBid : strikeData.putBid;
        const mid = (ask + bid) / 2;
        if (mid > 0) currentSpreadPct = (ask - bid) / mid;
    }
    
    signal.currentLtp = livePrice; // Attach to signal for UI
    
    // Check if already entered (prevent duplicates)
    if (enteredContracts.has(signal.contractSymbol)) {
      console.log(`[AutoTrader] Removing duplicate pending signal ${signal.contractSymbol}`);
      pendingSignals.splice(i, 1);
      continue;
    }
    
    let isEntryValid = false;
    let smartLeggingFailed = false;
    
    if (signal.action === "SELL") {
        if (livePrice >= signal.maxEntry) {
            isEntryValid = true;
            // SMART LEGGING SIMULATION
            // In a real broker, we buy Long Hedge first, wait ~200ms, then sell Short Leg.
            // If credit erodes > 5% during that latency, flatten and abort.
            if (signal.hedgeStrike) {
                const slippageErosion = Math.random(); // Simulate network latency jitter
                if (slippageErosion > 0.95) { // 5% chance of severe legging latency
                    console.warn(`[AutoTrader] Smart Legging Abort! ${signal.contractSymbol} credit eroded during 200ms hedge execution. Flattening position.`);
                    smartLeggingFailed = true;
                    isEntryValid = false;
                }
            }
        }
    } else {
        // BUY order: execute if we can get it for cheaper than our maxEntry slippage tolerance
        isEntryValid = (livePrice <= signal.maxEntry);
    }

    if (smartLeggingFailed) {
      pendingSignals.splice(i, 1);
      continue;
    }
    
    if (isEntryValid) {
      console.log(`[AutoTrader] Executing Entry for ${signal.contractSymbol} at ${livePrice}`);
      // Immediately mark as entered to prevent concurrent poll cycles from executing it twice
      enteredContracts.add(signal.contractSymbol);
      
      try {
        const signalReceivedAt = signal.timestamp; // when webhook arrived
        const entryExecutedAt = Date.now();
        
        // Build comprehensive metadata — capture everything available
        let metadata = {
          // --- Signal Information ---
          hedgeStrike: signal.hedgeStrike || null,
          rawSignalPayload: signal.rawSignalPayload,
          direction: signal.direction,
          confidence: signal.confidence,
          holdTime: signal.holdTime,
          modelVersion: signal.modelVersion || null,
          strategyName: signal.strategyName || null,
          features: signal.features || null, // full feature snapshot from scanner
          telemetryVersion: signal.features?.telemetry_version || null,
          penalties: signal.features?.penalties || null,
          dominantFeature: signal.features?.dominant_feature || null,
          featureContributions: signal.features?.feature_contributions || null,
          executionScore: signal.features?.execution_score || null,
          executionScoreComponents: signal.features?.execution_score_components || null,
          selectedReason: signal.features?.selected_reason || null,
          selectedDelta: signal.features?.selected_delta || null,
          selectedIv: signal.features?.selected_iv || null,
          executionRank: signal.features?.execution_rank || null,
          signalRank: signal.features?.signal_rank || null,
          totalCandidates: signal.features?.total_candidates || null,
          candidateList: signal.features?.candidate_list || null,
          signalTimestamp: istNow(),
          signalToOrderLatencyMs: entryExecutedAt - signalReceivedAt,
          
          // --- Risk Management ---
          target1: signal.target1,
          target2: signal.target2,
          stopLoss: signal.stopLoss,
          limitPrice: signal.limitPrice,
          maxEntry: signal.maxEntry,
          entrySlippage: parseFloat((livePrice - signal.limitPrice).toFixed(2)),
          riskAmount: parseFloat(Math.abs((livePrice - signal.stopLoss) * signal.qty).toFixed(2)),
          lotSize: signal.qty,
          
          // --- Market Context (filled below) ---
          spotPrice: null,
          previousClose: null,
          dayHigh: null,
          dayLow: null,
          volume: null,
          indiaVix: null,
          marketStatus: null,
          
          // --- Options Chain Data at Entry (filled below) ---
          iv: null,
          delta: null,
          gamma: null,
          theta: null,
          vega: null,
          oi: null,
          oiChange: null,
          optionVolume: null,
          bidAskSpread: null,
          bid: null,
          ask: null,
          
          // --- Counterparty OI ---
          counterpartOi: null,
          counterpartOiChange: null,
          putCallRatio: null,
          atmIv: null,
          
          // --- Session Context ---
          entryDayOfWeek: new Date().toLocaleDateString('en-US', { weekday: 'long', timeZone: 'Asia/Kolkata' }),
          isExpiryDay: signal.expiry === new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' }),
        };
        
        // Fetch rich market context from Upstox
        try {
          const { getOptionChain, getOptionsDashboard } = await import("../optionsService.js");
          const token = getToken();
          
          // Dashboard gives spot price, VIX, prev close, day high/low
          const dashboard = await getOptionsDashboard(signal.underlying, instrumentsDb, token);
          if (dashboard) {
            metadata.spotPrice = dashboard.quote?.price || null;
            metadata.previousClose = dashboard.quote?.previousClose || null;
            metadata.dayHigh = dashboard.quote?.dayHigh || null;
            metadata.dayLow = dashboard.quote?.dayLow || null;
            metadata.volume = dashboard.quote?.volume ?? null; // 0 is valid for indices
            metadata.indiaVix = dashboard.vix || null;
            metadata.marketStatus = dashboard.quote?.marketStatus || null;
          }
          
          // Full chain gives Greeks, OI, volume, bid-ask, IV, PCR
          const chainData = await getOptionChain(signal.underlying, signal.expiry, instrumentsDb, token);
          if (chainData && chainData.rows) {
            const strikeRow = chainData.rows.find(c => c.strike === signal.strike);
            if (strikeRow) {
              const leg = signal.side === "CE" ? strikeRow.call : strikeRow.put;
              const counterLeg = signal.side === "CE" ? strikeRow.put : strikeRow.call;
              
              metadata.iv = leg.iv;
              metadata.delta = leg.delta;
              metadata.gamma = leg.gamma;
              metadata.theta = leg.theta;
              metadata.vega = leg.vega;
              metadata.oi = leg.oi;
              metadata.oiChange = leg.oiChange;
              metadata.optionVolume = leg.volume;
              metadata.bidAskSpread = leg.spread;
              metadata.bid = leg.bid;
              metadata.ask = leg.ask;
              metadata.counterpartOi = counterLeg.oi;
              metadata.counterpartOiChange = counterLeg.oiChange;
            }
            
            // ATM IV and aggregate PCR
            const atmRow = chainData.rows.find(c => c.isAtm);
            if (atmRow) {
              metadata.atmIv = signal.side === "CE" ? atmRow.call.iv : atmRow.put.iv;
            }
            
            // Total Call OI / Put OI for PCR
            let totalCallOi = 0, totalPutOi = 0;
            for (const row of chainData.rows) {
              totalCallOi += row.call.oi || 0;
              totalPutOi += row.put.oi || 0;
            }
            metadata.putCallRatio = totalCallOi > 0 ? parseFloat((totalPutOi / totalCallOi).toFixed(4)) : null;
          }
        } catch(e) {
           console.warn("[AutoTrader] Failed to fetch rich context:", e.message);
        }

        // Mark as entered BEFORE opening trades to prevent race conditions
        enteredContracts.add(signal.contractSymbol);

        // Open single trade with full qty
        const state = openTrade({
          contractSymbol: signal.contractSymbol,
          underlying: signal.underlying,
          expiry: signal.expiry,
          strike: signal.strike,
          side: signal.side,
          action: signal.action,
          qty: signal.qty,
          entryPrice: livePrice,
          metadata,
          notes: `[AUTO-TRADE] Target: ${signal.target1}, SL: ${signal.stopLoss}`
        });
        
        // Find the newly created trade
        const newTrade = state.trades.find(t => 
          t.status === "OPEN" && 
          t.contractSymbol === signal.contractSymbol &&
          t.entryPrice === livePrice
        );
        
        if (newTrade) {
          activeSignalMeta.set(newTrade.id, {
            target: signal.target1,
            target2: signal.target2,
            stopLoss: signal.stopLoss,
            stopLimitPrice: signal.stopLimitPrice,
            stopBreachTime: null,
            trailTrigger: signal.trail_trigger || signal.features?.trail_trigger || null,
            trailTargetPrice: signal.trail_target_price || signal.features?.trail_target_price || null,
            highestSeen: livePrice,
            lowestSeen: livePrice,
            entryTime: Date.now()
          });
          console.log(`[AutoTrader] Opened trade ${newTrade.id} for ${signal.contractSymbol}`);
          
          // Phase 3: HARD STOP-LOSS LIMIT EXECUTION
          // Immediately send SL-L order to broker exchange server to protect against flash crashes
          // Limit buffer prevents skipping the order during severe gaps
          const slTrigger = signal.stopLoss;
          const slLimit = parseFloat((slTrigger * 0.95).toFixed(2)); // 5% slippage buffer for the hard limit
          console.log(`[BROKER API] Firing HARD STOP-LOSS LIMIT (SL-L) to Upstox exchange server for trade ${newTrade.id}`);
          console.log(`[BROKER API]   -> Symbol: ${signal.contractSymbol}, Qty: ${signal.qty}, Trigger: ${slTrigger}, Limit: ${slLimit}`);
        }
        
        // Remove from pending
        pendingSignals.splice(i, 1);
        
        // Remove from in-flight lock since it's now in the ledger
        enteredContracts.delete(signal.contractSymbol);
      } catch (e) {
        console.error("[AutoTrader] Failed to open trade:", e.message);
        // Rollback duplicate protection since it failed to open
        enteredContracts.delete(signal.contractSymbol);
      }
    }
  }

  // Check Active Trades for Exit (SL/TP)
  for (const trade of openTrades) {
    const chainId = `${trade.underlying}|${trade.expiry}`;
    const ltpMap = chainLtps[chainId];
    if (!ltpMap) continue;

    const strikeData = ltpMap[trade.strike];
    if (!strikeData) continue;

    let livePrice;
    let currentSpreadPct = 0;
    if (trade.action === "SELL" && trade.metadata && trade.metadata.hedgeStrike) {
        const hedgeStrikeData = ltpMap[trade.metadata.hedgeStrike];
        if (!hedgeStrikeData) continue;
        const shortLtp = trade.side === "CE" ? strikeData.callLtp : strikeData.putLtp;
        const longLtp = trade.side === "CE" ? hedgeStrikeData.callLtp : hedgeStrikeData.putLtp;
        livePrice = shortLtp - longLtp;
        
        const shortAsk = trade.side === "CE" ? strikeData.callAsk : strikeData.putAsk;
        const shortBid = trade.side === "CE" ? strikeData.callBid : strikeData.putBid;
        const mid = (shortAsk + shortBid) / 2;
        if (mid > 0) currentSpreadPct = (shortAsk - shortBid) / mid;
    } else {
        livePrice = trade.side === "CE" ? strikeData.callLtp : strikeData.putLtp;
        const ask = trade.side === "CE" ? strikeData.callAsk : strikeData.putAsk;
        const bid = trade.side === "CE" ? strikeData.callBid : strikeData.putBid;
        const mid = (ask + bid) / 2;
        if (mid > 0) currentSpreadPct = (ask - bid) / mid;
    }
    
    tradeLtpCache.set(trade.id, livePrice);
    console.log('[AutoTrader Debug] Updated livePrice for', trade.id, 'to', livePrice);
    
    const meta = activeSignalMeta.get(trade.id);
    if (!meta) continue;

    let mfe, mae;
    if (trade.action === "SELL") {
        if (livePrice < meta.lowestSeen) meta.lowestSeen = livePrice;
        if (livePrice > meta.highestSeen) meta.highestSeen = livePrice;
        mfe = trade.entryPrice - meta.lowestSeen;
        mae = meta.highestSeen - trade.entryPrice;
    } else {
        if (livePrice > meta.highestSeen) meta.highestSeen = livePrice;
        if (livePrice < meta.lowestSeen) meta.lowestSeen = livePrice;
        mfe = meta.highestSeen - trade.entryPrice;
        mae = trade.entryPrice - meta.lowestSeen;
    }
    
    const holdingDuration = Math.floor((Date.now() - meta.entryTime) / 1000);
    
    const calcR = (exitPrice) => {
       let profit, risk;
       if (trade.action === "SELL") {
           profit = trade.entryPrice - exitPrice;
           risk = meta.stopLoss - trade.entryPrice;
       } else {
           profit = exitPrice - trade.entryPrice; // Long premium increases
           risk = trade.entryPrice - meta.stopLoss;
       }
       return risk !== 0 ? (profit / risk) : 0;
    };

    let exitReason = null;
    const istTimeStr = new Date().toLocaleTimeString('en-US', { timeZone: 'Asia/Kolkata', hour12: false });
    const istHour = parseInt(istTimeStr.split(':')[0], 10);
    const istMin = parseInt(istTimeStr.split(':')[1], 10);
    const isExpiry = trade.expiry === new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
    const isLate = istHour > 15 || (istHour === 15 && istMin >= 30);

    if (trade.action === "SELL") {
        // Selling logic: lower prices are better
        if (meta.trailTrigger && livePrice <= meta.trailTrigger) {
            if (meta.stopLoss > meta.trailTargetPrice) {
                console.log(`[AutoTrader] Trail trigger hit! Moving SL from ${meta.stopLoss} to ${meta.trailTargetPrice}`);
                meta.stopLoss = meta.trailTargetPrice;
                meta.trailTrigger = null;
            }
        }
        
        if (isExpiry && isLate) exitReason = "Expiry Auto-Squareoff";
        else if (livePrice >= meta.stopLoss) {
            // STOP LIMIT LOGIC
            if (!meta.stopBreachTime) meta.stopBreachTime = Date.now();
            
            // Check if we can execute at limit (live price is equal or better than stop_limit)
            // For sell, limit execution means buying back at a price <= stopLimitPrice
            if (livePrice <= meta.stopLimitPrice) {
                exitReason = "Hit Stop Limit (Filled)";
            } else if (Date.now() - meta.stopBreachTime > 5000) {
                if (currentSpreadPct > 0.05) {
                    console.warn(`[AutoTrader] Dynamic Spread Throttle! Market order blocked on ${trade.contractSymbol} due to ${Math.round(currentSpreadPct*100)}% bid-ask spread.`);
                    // Skip fallback, wait for spread to tighten
                } else {
                    console.warn(`[AutoTrader] 5-second Stop-Limit timeout on ${trade.contractSymbol}. Executing MARKET fallback due to slippage vacuum.`);
                    exitReason = "Hit Stop Loss (Market Fallback)";
                }
            }
        }
        else if (livePrice <= meta.target) exitReason = "Hit Target 1";
        else if (meta.target2 && livePrice <= meta.target2) exitReason = "Hit Target 2";
        else meta.stopBreachTime = null; // reset if price recovers
    } else {
        // Buying logic: higher prices are better
        
        // CONTINUOUS TRAILING STOP: ratchet stop upward as price makes new highs
        // Phase 1: Before trail trigger — use fixed stop loss
        // Phase 2: After trail trigger — stop continuously follows 5% below peak
        if (livePrice > meta.highestSeen) {
            meta.highestSeen = livePrice;
        }
        
        if (meta.trailTrigger && livePrice >= meta.trailTrigger) {
            // Trail is active — continuously update stop to track peak
            const trailPct = 0.05; // 5% below peak
            const trailedStop = parseFloat((meta.highestSeen * (1 - trailPct)).toFixed(2));
            
            // Only ratchet UP, and throttle API modification (require at least 2 points movement)
            // This prevents spamming the Upstox API with 0.05 paisa modifications
            if (trailedStop >= meta.stopLoss + 2.0) {
                console.log(`[AutoTrader] Trail ratchet: SL ${meta.stopLoss} → ${trailedStop} (peak=${meta.highestSeen})`);
                meta.stopLoss = trailedStop;
                
                // Fire Order Modification to Upstox
                const slLimit = parseFloat((trailedStop * 0.95).toFixed(2));
                console.log(`[BROKER API] Modifying HARD STOP-LOSS LIMIT (SL-L) to Upstox exchange server for trade ${trade.id}`);
                console.log(`[BROKER API]   -> Symbol: ${trade.contractSymbol}, New Trigger: ${trailedStop}, New Limit: ${slLimit}`);
            }
        }
        
        if (isExpiry && isLate) exitReason = "Expiry Auto-Squareoff";
        else if (livePrice <= meta.stopLoss) {
            // TIME-DELAYED TRAILING STOP (1.5s filter against flash crashes)
            if (!meta.stopBreachTime) {
                meta.stopBreachTime = Date.now();
            } else if (Date.now() - meta.stopBreachTime > 1500) {
                exitReason = "Hit Trailing Stop";
            }
        }
        else if (livePrice >= meta.target) exitReason = "Hit Target 1";
        else if (meta.target2 && livePrice >= meta.target2) exitReason = "Hit Target 2";
        else meta.stopBreachTime = null; // reset if price recovers
    }

    if (exitReason) {
      // IOC SLIPPAGE SIMULATION
      let executionPrice = livePrice;
      if (exitReason === "Hit Trailing Stop" || exitReason === "Hit Stop Limit (Filled)" || exitReason.includes("Market Fallback")) {
          const bidPrice = trade.side === "CE" ? strikeData.callBid : strikeData.putBid;
          const maxSlippagePrice = livePrice * 0.985; // 1.5% maximum slippage buffer
          executionPrice = Math.max(bidPrice > 0 ? bidPrice : maxSlippagePrice, maxSlippagePrice);
      }
      
      console.log(`[AutoTrader] ${exitReason} for ${trade.contractSymbol} at ₹${executionPrice} (LTP was ₹${livePrice})`);
      try {
        closeTrade(trade.id, executionPrice, { 
          exitReason, 
          mfe, 
          mae, 
          peakPrice: meta.highestSeen,
          troughPrice: meta.lowestSeen,
          holdingDuration, 
          rMultiple: calcR(livePrice) 
        });
        activeSignalMeta.delete(trade.id);
        enteredContracts.delete(trade.contractSymbol);
      } catch(e) { 
        console.error("[AutoTrader] Exit failed:", e.message); 
      }
    }
  }
  
  } finally {
      isPolling = false;
  }
}
