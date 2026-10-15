import { parseTelegramSignal } from './services/signalParser.js';

const msg = `🚨 *TRADE SIGNAL*
━━━━━━━━━━━━━━━━━━━━━
📌 *NIFTY 2026-07-14 24100.0 CE*
📊 Direction: *BULLISH*
⚙️ Strategy: *Momentum Breakout*
━━━━━━━━━━━━━━━━━━━━━
👁 Last Seen: ₹189.15
✅ *LIMIT ORDER: ₹191.04*
🚫 Don't Chase: ₹192.93
💰 Lot Cost: ₹12,418
━━━━━━━━━━━━━━━━━━━━━
🛑 Stop Loss: ₹171.94
🎯 Target 1: ₹216.48
🎯 Target 2: ₹324.72
━━━━━━━━━━━━━━━━━━━━━
📈 Confidence: 0.6298
⏰ Enter Before: 12:49:53
⏳ Hold: 2-5 min`;

console.log(parseTelegramSignal(msg));
