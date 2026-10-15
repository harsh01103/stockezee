const fs = require('fs');

const ledgerPath = 'server/data/ledger.json';
const ledger = JSON.parse(fs.readFileSync(ledgerPath, 'utf8'));

console.log("Total trades:", ledger.trades.length);
const recentTrades = ledger.trades.slice(-5);
console.log(JSON.stringify(recentTrades, null, 2));
