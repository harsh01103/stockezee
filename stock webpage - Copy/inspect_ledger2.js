const fs = require('fs');
const ledgerPath = 'server/data/ledger.json';
const ledger = JSON.parse(fs.readFileSync(ledgerPath, 'utf8'));

const zeroExits = ledger.trades.filter(t => t.exitPrice === 0);
console.log("Trades with exitPrice 0:", zeroExits.length);
if (zeroExits.length > 0) {
  console.log("Last zero exit trade:", JSON.stringify(zeroExits[zeroExits.length - 1], null, 2));
}

const telegramExits = ledger.trades.filter(t => t.exitReason && t.exitReason.includes("Telegram"));
console.log("Trades closed via Telegram:", telegramExits.length);
if (telegramExits.length > 0) {
  console.log("Last telegram exit trade:", JSON.stringify(telegramExits[telegramExits.length - 1], null, 2));
}
