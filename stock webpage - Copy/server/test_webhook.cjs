const axios = require('axios');

const msg1 = `🚨 *TRADE SIGNAL*\n━━━━━━━━━━━━━━━━━━━━━\n📌 *BANKNIFTY 2026-06-30 57700.0 PE*\n📊 Direction: *BEARISH*\n━━━━━━━━━━━━━━━━━━━━━\n👁 Last Seen: ₹168.03\n✅ *LIMIT ORDER: ₹169.71*\n🚫 Don't Chase: ₹171.39\n💰 Lot Cost: ₹5,091\n━━━━━━━━━━━━━━━━━━━━━\n🛑 Stop Loss: ₹165.47\n🎯 Target 1: ₹177.86\n🎯 Target 2: ₹181.93\n━━━━━━━━━━━━━━━━━━━━━\n📈 Confidence: 0.7648\n⏰ Enter Before: 09:40:12\n⏳ Hold: 2-5 min`;

const msg2 = `🚨 *TRADE SIGNAL*\n━━━━━━━━━━━━━━━━━━━━━\n📌 *NIFTY 2026-06-30 23900.0 CE*\n📊 Direction: *BULLISH*\n━━━━━━━━━━━━━━━━━━━━━\n👁 Last Seen: ₹173.38\n✅ *LIMIT ORDER: ₹175.11*\n🚫 Don't Chase: ₹176.85\n💰 Lot Cost: ₹11,382\n━━━━━━━━━━━━━━━━━━━━━\n🛑 Stop Loss: ₹169.86\n🎯 Target 1: ₹185.62\n🎯 Target 2: ₹190.87\n━━━━━━━━━━━━━━━━━━━━━\n📈 Confidence: 0.6603\n⏰ Enter Before: 09:41:29\n⏳ Hold: 2-5 min`;

async function test() {
  try {
    const res1 = await axios.post('http://localhost:4000/api/signals/webhook', {
      message: msg1,
      features: { size_multiplier: 1.0 },
      model_version: 'v2.3',
      strategy_name: 'momentum_breakout'
    });
    console.log('BANKNIFTY Response:', res1.status, res1.data);
  } catch (err) {
    console.log('BANKNIFTY Error:', err.response ? err.response.data : err.message);
  }

  try {
    const res2 = await axios.post('http://localhost:4000/api/signals/webhook', {
      message: msg2,
      features: { size_multiplier: 1.0 },
      model_version: 'v2.3',
      strategy_name: 'momentum_breakout'
    });
    console.log('NIFTY Response:', res2.status, res2.data);
  } catch (err) {
    console.log('NIFTY Error:', err.response ? err.response.data : err.message);
  }
}
test();
