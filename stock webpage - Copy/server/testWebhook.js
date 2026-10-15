import axios from 'axios';
const msg = `🚨 TRADE SIGNAL
━━━━━━━━━━━━━━━━━━━━━
📌 BANKNIFTY 2026-06-30 57400.0 CE
📊 Direction: BULLISH
━━━━━━━━━━━━━━━━━━━━━
👁 Last Seen: ₹460.12
✅ LIMIT ORDER: ₹464.72
🚫 Don't Chase: ₹469.32
💰 Lot Cost: ₹13,942
━━━━━━━━━━━━━━━━━━━━━
🛑 Stop Loss: ₹450.78
🎯 Target 1: ₹487.96
🎯 Target 2: ₹506.54
━━━━━━━━━━━━━━━━━━━━━
📈 Confidence: 0.6732
⏰ Enter Before: 14:50:46
⏳ Hold: 3-8 min`;

axios.post('http://localhost:4000/api/signals/webhook', { message: msg })
  .then(r => console.log(r.data))
  .catch(e => console.error(e.response ? e.response.data : e.message));
