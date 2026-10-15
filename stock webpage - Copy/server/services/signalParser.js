export function parseTelegramSignal(rawText) {
  try {
    // Strip telegram markdown asterisks to allow robust matching
    const text = rawText.replace(/\*/g, '');
    const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    
    // Find contract details line (📌 BANKNIFTY 2026-06-30 57400.0 CE)
    // Avoid strictly matching emojis as they might change
    const contractLine = lines.find(l => l.includes('CE') || l.includes('PE'));
    if (!contractLine) throw new Error("Could not find contract details (CE/PE)");
    
    // contractLine might have emoji at the start, e.g. "📌 BANKNIFTY ..."
    // Let's strip any non-ASCII characters from the start of the line or just split and grab the last 4 tokens
    const rawParts = contractLine.split(' ').filter(p => p.trim() !== '');
    // Expect the last 4 parts to be: ["BANKNIFTY", "2026-06-30", "57400.0", "CE"]
    if (rawParts.length < 4) throw new Error("Invalid contract format");
    
    const parts = rawParts.slice(-4);
    
    const underlying = parts[0];
    const expiry = parts[1];
    const strike = parseFloat(parts[2]);
    const side = parts[3];
    
    const contractSymbol = `${underlying} ${expiry} ${strike} ${side}`;

    // Extract execution prices
    const limitLine = lines.find(l => l.includes('LIMIT ORDER:'));
    const limitPrice = limitLine ? parseFloat(limitLine.split('₹')[1].replace(/,/g, '')) : null;

    // Don't Chase is optional — if absent, use limitPrice * 1.05 as a sensible max
    const dontChaseLine = lines.find(l => l.includes("Don't Chase:"));
    const maxEntry = dontChaseLine ? parseFloat(dontChaseLine.split('₹')[1].replace(/,/g, '')) : (limitPrice ? limitPrice * 1.05 : null);

    // Extract Risk Management
    const slLine = lines.find(l => l.includes('Stop Loss:'));
    const stopLoss = slLine ? parseFloat(slLine.split('₹')[1].replace(/,/g, '')) : null;

    const t1Line = lines.find(l => l.includes('Target 1:'));
    const target1 = t1Line ? parseFloat(t1Line.split('₹')[1].replace(/,/g, '')) : null;

    const t2Line = lines.find(l => l.includes('Target 2:'));
    const target2 = t2Line ? parseFloat(t2Line.split('₹')[1].replace(/,/g, '')) : null;

    const dirLine = lines.find(l => l.includes('Direction:'));
    const direction = dirLine ? dirLine.split(':')[1].trim() : "BULLISH";
    
    const stratLine = lines.find(l => l.includes('Strategy:'));
    const strategy = stratLine ? stratLine.split(':')[1].trim() : "";
    const action = strategy.includes("Credit Spread") ? "SELL" : "BUY";

    const confLine = lines.find(l => l.includes('Confidence:'));
    const confidence = confLine ? parseFloat(confLine.split(':')[1].trim()) : null;

    // Extract Hedge Strike for Credit Spreads
    const hedgeLine = lines.find(l => l.includes('HEDGE LEG:'));
    let hedgeStrike = null;
    if (hedgeLine) {
        // e.g. 🛡️ HEDGE LEG: Buy BANKNIFTY 2026-06-30 57900.0 CE
        const parts = hedgeLine.split(' ');
        // Find the numeric strike by looking at all parts, avoiding date strings like YYYY-MM-DD
        const numericParts = parts.filter(p => !p.includes('-')).map(p => parseFloat(p)).filter(p => !isNaN(p) && p > 1000);
        if (numericParts.length > 0) {
             hedgeStrike = numericParts[0];
        } else {
             // Fallback
             const sMatch = hedgeLine.match(/(?<!-)\b\d{4,}\b/);
             if (sMatch) hedgeStrike = parseFloat(sMatch[0]);
        }
    }

    // Hold time is optional — don't fail if missing
    const holdLine = lines.find(l => l.includes('Hold:'));
    const holdTime = holdLine ? holdLine.split(':')[1].trim() : null;

    if (!limitPrice || !stopLoss || !target1) {
      throw new Error("Missing required prices (Limit, SL, or Target1)");
    }

    // Updated lot sizes per SEBI/NSE effective rules
    const LOT_SIZES = {
      NIFTY: 65,
      BANKNIFTY: 30,
      FINNIFTY: 60,
      MIDCPNIFTY: 120,
      NIFTYNXT50: 25,
      SENSEX: 20,
      BANKEX: 30,
    };
    const qty = LOT_SIZES[underlying] || 15;

    return {
      underlying,
      expiry,
      strike,
      hedgeStrike,
      side,
      contractSymbol,
      limitPrice,
      maxEntry,
      stopLoss,
      stopLimitPrice: action === "SELL" ? parseFloat((stopLoss * 1.01).toFixed(2)) : parseFloat((stopLoss * 0.99).toFixed(2)),
      target1,
      target2,
      action, // Dynamic BUY or SELL
      qty,
      direction,
      confidence,
      holdTime,
      rawSignalPayload: rawText
    };
  } catch (error) {
    console.error("Signal parsing failed:", error.message);
    console.error("Raw text was:", rawText);
    return null;
  }
}
