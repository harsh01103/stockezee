import axios from "axios";
import { parseTelegramSignal } from "./signalParser.js";
import { queueSignal, getPendingSignals, clearPendingSignals, getActiveTradeLtps } from "./autoTrader.js";
import { getLedgerState, closeTrade } from "./ledgerService.js";
import fs from "fs";

let isPolling = false;
let lastUpdateId = 0;
let knownChatId = null;
let heartbeatInterval = null;

export function startTelegramPoller() {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (!token) {
    console.warn("[TelegramPoller] No TELEGRAM_BOT_TOKEN found in .env, skipping Telegram polling.");
    return;
  }
  
  // Make sure we only start once
  if (isPolling) return;
  isPolling = true;

  console.log(`[TelegramPoller] Starting Telegram listener for bot token...`);
  
  // Register bot commands menu
  axios.post(`https://api.telegram.org/bot${token}/setMyCommands`, {
    commands: [
      { command: 'status', description: 'Show system summary and P&L' },
      { command: 'active', description: 'Show open positions' },
      { command: 'queued', description: 'Show queued/pending signals' },
      { command: 'recent', description: 'Show 5 most recent trades' },
      { command: 'close', description: 'Close a specific trade by number' },
      { command: 'flatten', description: 'Close all open trades instantly' },
      { command: 'clear', description: 'Clear all queued signals' },
      { command: 'ping', description: 'Check if bot is alive' },
      { command: 'kill', description: 'Panic mode: Close trades & shutdown' },
      { command: 'pause', description: 'Halt new entries (trailing stops run)' },
      { command: 'resume', description: 'Resume taking new entries' },
      { command: 'engine', description: 'View live macro regime & telemetry' },
      { command: 'ideas', description: 'View latest engine ideas & rejection reasons' },
      { command: 'maxloss', description: 'Update daily max loss (e.g., /maxloss -1000)' },
      { command: 'lockprofit', description: 'Lock in current profit minus buffer' },
      { command: 'block', description: 'Block a symbol (e.g., /block NIFTY)' },
      { command: 'trail', description: 'Tighten stop on trade (e.g., /trail 1 tight)' },
      { command: 'flip', description: 'Reverse an active trade instantly' },
      { command: 'force_cas', description: 'Force Closing Auction Session now' }
    ]
  }).catch(err => console.error("[TelegramPoller] Failed to set bot menu:", err.message));

  pollTelegram(token);
  startHeartbeatMonitor(token);
}

async function pollTelegram(token) {
  try {
    const url = `https://api.telegram.org/bot${token}/getUpdates?offset=${lastUpdateId + 1}&timeout=30`;
    const response = await axios.get(url);
    
    if (response.data && response.data.ok) {
      const updates = response.data.result;
      
      for (const update of updates) {
        lastUpdateId = Math.max(lastUpdateId, update.update_id);
        
        const message = update.message || update.channel_post;
        if (message && message.text) {
          const text = message.text.trim();
          knownChatId = message.chat.id;
          
          // ── HELP COMMAND ──
          if (text === "/start" || text === "/help") {
             const helpText = `👋 *Stock Auto-Trader Bot*\n\n*General:*\n/status - Show summary and P&L\n/active - Show open positions\n/queued - Pending signals\n/recent - 5 most recent trades\n/ping - Health check\n\n*Trade Control:*\n/close <num> - Close specific trade\n/flip <num> - Reverse trade\n/trail <num> tight - Tighten stop\n/flatten - Close ALL active & clear queue\n/clear - Clear queued\n\n*Algo Control:*\n/pause & /resume - Halt/Resume entries\n/engine - Live telemetry\n/ideas - Engine thoughts & rejections\n/maxloss <amount> - Set daily max loss\n/lockprofit - Lock current profit as floor\n/block <symbol> - Prevent symbol trading\n/force_cas - Force Closing Auction check\n\n*Emergency:*\n/kill - Panic close trades & shutdown`;
             try {
                await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: helpText, parse_mode: 'Markdown' });
             } catch(e) {}
          }
          
          // ── STATUS COMMAND ──
          else if (text === "/status" || text === "/summary") {
            const ledger = getLedgerState();
            const activeCount = ledger.trades.filter(t => t.status === "OPEN").length;
            const ledgerCount = ledger.trades.length;
            const queuedCount = getPendingSignals().length;
            
            const fC = (val) => Number(val).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            const balance = fC(ledger.balance);
            
            const totalPnl = ledger.totalPnl || 0;
            const totalPnlFormatted = totalPnl >= 0 ? `+₹${fC(totalPnl)}` : `-₹${fC(Math.abs(totalPnl))}`;
            
            const avgProfit = ledger.avgProfit || 0;
            const avgProfitFormatted = avgProfit >= 0 ? `+₹${fC(avgProfit)}` : `-₹${fC(Math.abs(avgProfit))}`;
            
            const prevTrade = ledger.latestTradePnl || 0;
            const prevTradeFormatted = `₹${fC(prevTrade)}`;
            
            const responseText = `📊 *System Status*\n\n🟢 *Active*: ${activeCount}\n📚 *Ledger*: ${ledgerCount}\n⏳ *Queued*: ${queuedCount}\n\n💰 *Balance*: ₹${balance}\n📈 *Total P&L*: ${totalPnlFormatted}\n🎯 *Avg Profit / Trade*: ${avgProfitFormatted}\n🔄 *Prev Trade*: ${prevTradeFormatted}`;

            try {
               await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, {
                 chat_id: message.chat.id,
                 text: responseText,
                 parse_mode: 'Markdown'
               });
            } catch (err) {
               console.error("[TelegramPoller] Failed to send status:", err.message);
            }
          }

          // ── ACTIVE TRADES COMMAND ──
          else if (text === "/active") {
             const ledger = getLedgerState();
             const openTrades = ledger.trades.filter(t => t.status === "OPEN");
             let resText = `🟢 *Active Positions (${openTrades.length})*\n\n`;
             if (openTrades.length === 0) {
                 resText += "No active trades at the moment.";
             } else {
                 openTrades.forEach((t, i) => {
                     resText += `${i+1}. *${t.contractSymbol}*\n   Entry: ₹${t.entryPrice} | Qty: ${t.qty}\n   (To close this trade, type \`/close ${i+1}\`)\n\n`;
                 });
             }
             try {
                await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: resText, parse_mode: 'Markdown' });
             } catch(e) {}
          }

          // ── RECENT TRADES COMMAND ──
          else if (text === "/recent") {
             const ledger = getLedgerState();
             const closedTrades = ledger.trades.filter(t => t.status === "CLOSED").slice(0, 5);
             let resText = `🔄 *Recent Trades (Last 5)*\n\n`;
             if (closedTrades.length === 0) {
                 resText += "No closed trades yet.";
             } else {
                 closedTrades.forEach((t, i) => {
                     const pnl = t.netPnl !== undefined ? t.netPnl : (t.pnl || 0);
                     const pnlStr = pnl >= 0 ? `🟢 +₹${pnl.toFixed(2)}` : `🔴 -₹${Math.abs(pnl).toFixed(2)}`;
                     resText += `${i+1}. *${t.contractSymbol}*\n   ${pnlStr} (Exit: ₹${t.exitPrice})\n`;
                 });
             }
             try {
                await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: resText, parse_mode: 'Markdown' });
             } catch(e) {}
          }

          // ── FLATTEN COMMAND ──
          else if (text === "/flatten") {
             const ledger = getLedgerState();
             const openTrades = ledger.trades.filter(t => t.status === "OPEN");
             const ltps = getActiveTradeLtps();
             let count = 0;
             for (const trade of openTrades) {
                 const exitPrc = ltps[trade.id] || trade.entryPrice;
                 closeTrade(trade.id, exitPrc, { exitReason: "Manual Flatten" });
                 count++;
             }
             const cleared = clearPendingSignals();
             const resText = `🧹 *Flatten Complete*\n\nClosed ${count} active positions.\nCleared ${cleared} queued signals.`;
             try {
                await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: resText, parse_mode: 'Markdown' });
             } catch(e) {}
          }

          // ── CLEAR COMMAND ──
          else if (text === "/clear") {
             const cleared = clearPendingSignals();
             const resText = `🗑️ *Queue Cleared*\n\nCleared ${cleared} queued signals.`;
             try {
                await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: resText, parse_mode: 'Markdown' });
             } catch(e) {}
          }

          // ── QUEUED COMMAND ──
          else if (text === "/queued") {
             const pending = getPendingSignals();
             let resText = `⏳ *Queued Signals (${pending.length})*\n\n`;
             if (pending.length === 0) {
                 resText += "No queued signals at the moment.";
             } else {
                 pending.forEach((s, i) => {
                     resText += `${i+1}. *${s.contractSymbol}*\n   Max Entry: ₹${s.maxEntry} | Target: ₹${s.target1} | SL: ₹${s.stopLoss}\n\n`;
                 });
             }
             try {
                await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: resText, parse_mode: 'Markdown' });
             } catch(e) {}
          }

          // ── PING COMMAND ──
          else if (text === "/ping") {
             let runnerStatus = "🔴 Down";
             let recorderStatus = "🔴 Down";
             let reason = "";
             let runnerOk = false;
             let recorderOk = false;
             const now = Date.now() / 1000;

             const defaultOptionsDir = path.resolve(__dirname, "../../../OPTIONS");
             const runnerHbPath = path.join(process.env.OPTIONS_DIR || defaultOptionsDir, "reports", "heartbeat.txt");
             const recHbPath = path.join(process.env.OPTIONS_DIR || defaultOptionsDir, "runtime", "heartbeat.json");

             // Check Runner
             try {
                if (fs.existsSync(runnerHbPath)) {
                   const runnerTs = parseFloat(fs.readFileSync(runnerHbPath, "utf-8"));
                   if (now - runnerTs < 15) {
                      runnerStatus = "🟢 Up";
                      runnerOk = true;
                   } else {
                      runnerStatus = "🟡 Stale";
                      reason += "Runner heartbeat is older than 15s (it might be stuck/dead).\n";
                   }
                } else {
                   reason += "Runner heartbeat file missing (runner.py is not running).\n";
                }
             } catch(e) { reason += "Error reading Runner heartbeat.\n"; }

             // Check Recorder
             try {
                if (fs.existsSync(recHbPath)) {
                   const recHb = JSON.parse(fs.readFileSync(recHbPath, "utf-8"));
                   if (now - recHb.last_tick < 15) {
                      recorderStatus = "🟢 Up";
                      recorderOk = true;
                   } else {
                      recorderStatus = "🟡 Stale";
                      reason += "Recorder heartbeat is older than 15s (it might be disconnected).\n";
                   }
                } else {
                   reason += "Recorder heartbeat file missing (recorder.py is not running).\n";
                }
             } catch(e) { reason += "Error reading Recorder heartbeat.\n"; }

             let resText = `🏓 *Pong!*\n\n*Runner (Python Engine):* ${runnerStatus}\n*Recorder (Market Data):* ${recorderStatus}\n`;
             if (!runnerOk || !recorderOk) {
                 resText += `\n⚠️ *Issues Detected:*\n${reason}`;
             } else {
                 resText += `\n✅ Both systems are running perfectly!`;
             }

             try {
                await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: resText, parse_mode: 'Markdown' });
             } catch(e) {}
          }

          // ── ALGO CONTROL COMMANDS ──
          else if (text === "/pause") {
             const pausePath = "C:/Users/kpn_i/.gemini/antigravity-ide/scratch/OPTIONS/config/pause.flag";
             fs.writeFileSync(pausePath, "true");
             try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: "⏸️ *Engine Paused*\n\nNew trades will NOT be taken. Trailing stops remain active.", parse_mode: 'Markdown' }); } catch(e) {}
          }
          else if (text === "/resume") {
             const pausePath = "C:/Users/kpn_i/.gemini/antigravity-ide/scratch/OPTIONS/config/pause.flag";
             if (fs.existsSync(pausePath)) fs.unlinkSync(pausePath);
             try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: "▶️ *Engine Resumed*\n\nSignal generation is active.", parse_mode: 'Markdown' }); } catch(e) {}
          }
          else if (text === "/engine") {
             const telePath = "C:/Users/kpn_i/.gemini/antigravity-ide/scratch/OPTIONS/config/telemetry.json";
             if (fs.existsSync(telePath)) {
                try {
                    const tele = JSON.parse(fs.readFileSync(telePath, "utf-8"));
                    let resText = `🧠 *Engine Snapshot (${tele.timestamp})*\n\n`;
                    resText += `*NIFTY*: ${tele.NIFTY.regime} (OI: ${tele.NIFTY.oi_net}%)\n`;
                    resText += `*BANKNIFTY*: ${tele.BANKNIFTY.regime} (OI: ${tele.BANKNIFTY.oi_net}%)\n\n`;
                    resText += `*Active Engines*: ${tele.active_engines}\n\n`;
                    resText += `*Nifty ATM*: ${tele.NIFTY.atm_strike} (CE: ₹${tele.NIFTY.ce_prem} / PE: ₹${tele.NIFTY.pe_prem})\n`;
                    resText += `*Bank ATM*: ${tele.BANKNIFTY.atm_strike} (CE: ₹${tele.BANKNIFTY.ce_prem} / PE: ₹${tele.BANKNIFTY.pe_prem})`;
                    await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: resText, parse_mode: 'Markdown' });
                } catch(e) {
                    await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: "❌ Error reading telemetry." });
                }
             } else {
                try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: "❌ Telemetry file not found. Is runner.py running?" }); } catch(e) {}
             }
          }
          else if (text === "/ideas") {
             const ideasPath = "C:/Users/kpn_i/.gemini/antigravity-ide/scratch/OPTIONS/reports/all_generated_ideas.jsonl";
             if (fs.existsSync(ideasPath)) {
                try {
                   const lines = fs.readFileSync(ideasPath, "utf-8").trim().split("\n");
                   const recent = lines.slice(-5).reverse(); // Last 5 ideas, newest first
                   let resText = `🧠 *Engine Idea Stream (Last 5)*\n\n`;
                   
                   for (const line of recent) {
                       if (!line) continue;
                       const idea = JSON.parse(line);
                       const status = idea.is_executable ? "✅ *APPROVED*" : "❌ *REJECTED*";
                       resText += `${status}\n`;
                       resText += `*${idea.underlying}* ${idea.strike} ${idea.option_type}\n`;
                       resText += `Time: ${idea.timestamp}\n`;
                       resText += `Confidence: ${(idea.confidence * 100).toFixed(1)}%\n`;
                       if (!idea.is_executable) {
                           resText += `Reason: \`${idea.rejection_reason}\`\n`;
                       }
                       resText += `\n`;
                   }
                   
                   await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: resText, parse_mode: 'Markdown' });
                } catch(e) {
                   try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: "❌ Failed to read ideas stream." }); } catch(err) {}
                }
             } else {
                try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: "❌ Idea stream not found. Engine hasn't generated any ideas yet." }); } catch(e) {}
             }
          }
          else if (text.startsWith("/maxloss")) {
             const amt = parseInt(text.split(" ")[1], 10);
             if (!isNaN(amt)) {
                 const lossPath = "C:/Users/kpn_i/.gemini/antigravity-ide/scratch/OPTIONS/config/maxloss.json";
                 fs.writeFileSync(lossPath, JSON.stringify({ amount: amt }));
                 try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: `📉 *Max Loss Updated*\n\nDaily limit is now set to ₹${amt}`, parse_mode: 'Markdown' }); } catch(e) {}
             }
          }
          else if (text.startsWith("/block")) {
             const sym = text.split(" ")[1]?.toUpperCase();
             if (sym) {
                 const blkPath = "C:/Users/kpn_i/.gemini/antigravity-ide/scratch/OPTIONS/config/block.json";
                 let blocked = [];
                 if (fs.existsSync(blkPath)) blocked = JSON.parse(fs.readFileSync(blkPath, "utf-8"));
                 if (!blocked.includes(sym)) blocked.push(sym);
                 fs.writeFileSync(blkPath, JSON.stringify(blocked));
                 try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: `🛑 *Symbol Blocked*\n\n${sym} added to blocklist.`, parse_mode: 'Markdown' }); } catch(e) {}
             }
          }
          else if (text === "/lockprofit") {
             const ledger = getLedgerState();
             const pnl = ledger.totalPnl || 0;
             const amt = Math.floor(pnl - 500); // 500 Rs buffer
             const lossPath = "C:/Users/kpn_i/.gemini/antigravity-ide/scratch/OPTIONS/config/maxloss.json";
             fs.writeFileSync(lossPath, JSON.stringify({ amount: amt }));
             try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: `🔒 *Profit Locked*\n\nCurrent PnL: ₹${pnl.toFixed(2)}\nMax Loss floor set to: ₹${amt}\n\nIf PnL drops below this, system will halt.`, parse_mode: 'Markdown' }); } catch(e) {}
          }
          else if (text === "/force_cas") {
             const casPath = "C:/Users/kpn_i/.gemini/antigravity-ide/scratch/OPTIONS/config/force_cas.flag";
             fs.writeFileSync(casPath, "true");
             try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: "⚡ *CAS Engine Forced*\n\nClosing Auction Session will run on next cycle.", parse_mode: 'Markdown' }); } catch(e) {}
          }
          else if (text.startsWith("/trail")) {
             const args = text.split(" ");
             const idx = parseInt(args[1], 10);
             if (!isNaN(idx)) {
                 const ledger = getLedgerState();
                 const openTrades = ledger.trades.filter(t => t.status === "OPEN");
                 if (idx > 0 && idx <= openTrades.length) {
                     const trade = openTrades[idx - 1];
                     const trailPath = "C:/Users/kpn_i/.gemini/antigravity-ide/scratch/OPTIONS/config/trail_overrides.json";
                     let overrides = {};
                     if (fs.existsSync(trailPath)) overrides = JSON.parse(fs.readFileSync(trailPath, "utf-8"));
                     overrides[trade.id] = "tight";
                     fs.writeFileSync(trailPath, JSON.stringify(overrides));
                     try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: `🎯 *Trailing Tightened*\n\nTrade #${idx} (${trade.contractSymbol}) will have its stop pulled to breakeven/trail dynamically.`, parse_mode: 'Markdown' }); } catch(e) {}
                 } else {
                     try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: `❌ Trade #${idx} not found.` }); } catch(e) {}
                 }
             }
          }
          else if (text.startsWith("/flip")) {
             const args = text.split(" ");
             const idx = parseInt(args[1], 10);
             if (!isNaN(idx)) {
                 const ledger = getLedgerState();
                 const openTrades = ledger.trades.filter(t => t.status === "OPEN");
                 if (idx > 0 && idx <= openTrades.length) {
                     const trade = openTrades[idx - 1];
                     const ltps = getActiveTradeLtps();
                     const exitPrc = ltps[trade.id] || trade.entryPrice;
                     closeTrade(trade.id, exitPrc, { exitReason: "Manual Flip" });
                     
                     // Send opposing signal
                     const oppType = trade.optionType === "CE" ? "PE" : "CE";
                     const oppSignal = {
                         underlying: trade.underlying,
                         expiry: trade.expiry,
                         strike: trade.strike,
                         option_type: oppType,
                         action: trade.action || "BUY",
                         entry_price: exitPrc,
                         target1: exitPrc * 1.5,
                         stop_loss: exitPrc * 0.5,
                         confidence_score: 0.99,
                         _engine: "Manual Flip"
                     };
                     queueSignal(oppSignal);
                     try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: `📈 *Flipping Trade #${idx}*\n\nClosed ${trade.contractSymbol}.\nQueued ${trade.underlying} ${trade.strike} ${oppType}.`, parse_mode: 'Markdown' }); } catch(e) {}
                 } else {
                     try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: `❌ Trade #${idx} not found.` }); } catch(e) {}
                 }
             }
          }

          // ── CLOSE COMMAND ──
          else if (text.startsWith("/close")) {
             const args = text.split(" ");
             const index = parseInt(args[1], 10);
             if (isNaN(index) || index <= 0) {
                 try {
                     await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: "❌ Invalid format. Use `/close <number>` (e.g. `/close 1`)", parse_mode: 'Markdown' });
                 } catch(e) {}
             } else {
                 const ledger = getLedgerState();
                 const openTrades = ledger.trades.filter(t => t.status === "OPEN");
                 if (index > openTrades.length) {
                     try {
                         await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: `❌ Trade #${index} not found. You only have ${openTrades.length} active trades.`, parse_mode: 'Markdown' });
                     } catch(e) {}
                 } else {
                     const trade = openTrades[index - 1];
                     const ltps = getActiveTradeLtps();
                     const exitPrc = ltps[trade.id] || trade.entryPrice;
                     try {
                         closeTrade(trade.id, exitPrc, { exitReason: "Manual Close (Telegram)" });
                         const resText = `✅ *Closed Trade #${index}*\n\nClosed *${trade.contractSymbol}* at roughly ₹${exitPrc}.`;
                         await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: resText, parse_mode: 'Markdown' });
                     } catch (err) {
                         await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: message.chat.id, text: `❌ Error closing trade: ${err.message}` });
                     }
                 }
             }
          }

          // ── GLOBAL KILL SWITCH ──
          else if (text === "/panic" || text === "/kill") {
             console.error("[TelegramPoller] 🚨 KILL SWITCH ACTIVATED VIA TELEGRAM 🚨");
             console.error("[BROKER API] Firing MARKET ORDERS to flatten all active positions...");
             
             // 1. Close all active positions
             const ledger = getLedgerState();
             const ltps = getActiveTradeLtps();
             for (const trade of ledger.trades) {
                 if (trade.status === "OPEN") {
                     // In a real broker, fire market order here
                     const exitPrc = ltps[trade.id] || trade.entryPrice;
                     closeTrade(trade.id, exitPrc, { exitReason: "KILL SWITCH" });
                     console.log(`[BROKER API] Flatted trade ${trade.id}`);
                 }
             }
             // 2. Write panic flag for watchdog.py to prevent restarts, and kill Node.js
             const panicPath = "C:/Users/kpn_i/.gemini/antigravity-ide/scratch/OPTIONS/reports/panic.flag";
             fs.writeFileSync(panicPath, "true");
             console.error("Shutting down Node.js auto-trader immediately.");
             process.exit(1);
          }
            
          // Check if it looks like a trade signal
          if (text.includes("TRADE SIGNAL") || text.includes("LIMIT ORDER")) {
            console.log(`[TelegramPoller] Received Trade Signal from Chat ${message.chat.id}`);
            const parsed = parseTelegramSignal(text);
            
            if (parsed) {
              queueSignal(parsed);
            } else {
              console.warn(`[TelegramPoller] Failed to parse message from Chat ${message.chat.id}`);
            }
          }
        }
      }
    }
  } catch (error) {
    console.error("[TelegramPoller] Error pulling updates:", error.message);
  }

  // Continue polling immediately (or after a delay on error)
  if (isPolling) {
    setTimeout(() => pollTelegram(token), 3000);
  }
}

// ── AUTOMATIC HEARTBEAT MONITOR ──
function startHeartbeatMonitor(token) {
  if (heartbeatInterval) clearInterval(heartbeatInterval);
  
  let runnerAlerted = false;
  let recorderAlerted = false;

  heartbeatInterval = setInterval(async () => {
     if (!knownChatId) return; // Cannot alert if we don't know who to message

     const defaultOptionsDir = path.resolve(__dirname, "../../../OPTIONS");
     const runnerPath = path.join(process.env.OPTIONS_DIR || defaultOptionsDir, "reports", "heartbeat.txt");
     const recorderPath = path.join(process.env.OPTIONS_DIR || defaultOptionsDir, "runtime", "heartbeat.json");
     
     const now = Date.now();
     const MAX_AGE_MS = 120_000; // 2 minutes

     // Check Runner
     if (fs.existsSync(runnerPath)) {
        const mtime = fs.statSync(runnerPath).mtimeMs;
        if (now - mtime > MAX_AGE_MS) {
           if (!runnerAlerted) {
              runnerAlerted = true;
              try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: knownChatId, text: "🚨 *ALERT: RUNNER DOWN*\n\n`runner.py` hasn't updated its heartbeat in over 2 minutes!", parse_mode: 'Markdown' }); } catch(e) {}
           }
        } else {
           if (runnerAlerted) {
              runnerAlerted = false;
              try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: knownChatId, text: "✅ *RECOVERY: RUNNER*\n\n`runner.py` is back online.", parse_mode: 'Markdown' }); } catch(e) {}
           }
        }
     } else if (!runnerAlerted) {
        runnerAlerted = true;
        try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: knownChatId, text: "🚨 *ALERT: RUNNER DOWN*\n\n`runner.py` heartbeat file is missing!", parse_mode: 'Markdown' }); } catch(e) {}
     }

     // Check Recorder
     if (fs.existsSync(recorderPath)) {
        try {
           const recorderData = JSON.parse(fs.readFileSync(recorderPath, "utf-8"));
           if (recorderData.last_heartbeat) {
              const recorderMtime = new Date(recorderData.last_heartbeat).getTime();
              if (now - recorderMtime > MAX_AGE_MS) {
                 if (!recorderAlerted) {
                    recorderAlerted = true;
                    try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: knownChatId, text: "🚨 *ALERT: RECORDER DOWN*\n\n`recorder.py` hasn't sent a heartbeat in over 2 minutes!", parse_mode: 'Markdown' }); } catch(e) {}
                 }
              } else {
                 if (recorderAlerted) {
                    recorderAlerted = false;
                    try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: knownChatId, text: "✅ *RECOVERY: RECORDER*\n\n`recorder.py` is back online.", parse_mode: 'Markdown' }); } catch(e) {}
                 }
              }
           }
        } catch(e) {}
     } else if (!recorderAlerted) {
        recorderAlerted = true;
        try { await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, { chat_id: knownChatId, text: "🚨 *ALERT: RECORDER DOWN*\n\n`recorder.py` heartbeat file is missing!", parse_mode: 'Markdown' }); } catch(e) {}
     }

  }, 60_000); // Check every 60 seconds
}
