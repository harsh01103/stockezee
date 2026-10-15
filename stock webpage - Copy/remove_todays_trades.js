const fs = require('fs');
const ledgerPath = 'server/data/ledger.json';
const ledger = JSON.parse(fs.readFileSync(ledgerPath, 'utf8'));

const TODAY = '2026-10-13';
let removedCount = 0;
let restoredBalance = 0;

const keptTrades = [];

for (const trade of ledger.trades) {
  const isToday = (trade.timestamp && trade.timestamp.startsWith(TODAY)) || 
                  (trade.exitTimestamp && trade.exitTimestamp.startsWith(TODAY));
  if (isToday) {
    // This is a trade from today
    removedCount++;
    
    // Revert balance changes
    if (trade.entryCharges && trade.entryCharges.total) {
      ledger.balance += trade.entryCharges.total;
      restoredBalance += trade.entryCharges.total;
    }
    
    if (trade.status === 'CLOSED') {
      if (trade.grossPnl) {
        ledger.balance -= trade.grossPnl;
        restoredBalance -= trade.grossPnl;
      }
      if (trade.exitCharges && trade.exitCharges.total) {
        ledger.balance += trade.exitCharges.total;
        restoredBalance += trade.exitCharges.total;
      }
    }
  } else {
    keptTrades.push(trade);
  }
}

console.log(`Found and removing ${removedCount} trades from today (${TODAY}).`);
console.log(`Balance adjusted by ${restoredBalance}. New balance: ${ledger.balance}`);

ledger.trades = keptTrades;
fs.writeFileSync(ledgerPath, JSON.stringify(ledger, null, 2), 'utf8');
console.log('ledger.json updated.');
