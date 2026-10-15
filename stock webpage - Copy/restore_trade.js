const fs = require('fs');

const ledgerPath = 'server/data/ledger.json';
const ledger = JSON.parse(fs.readFileSync(ledgerPath, 'utf8'));

// Find the last closed trade
const lastClosedTradeIndex = ledger.trades.reduce((latestIdx, t, idx) => {
    return t.status === "CLOSED" ? idx : latestIdx;
}, -1);

if (lastClosedTradeIndex !== -1) {
    const trade = ledger.trades[lastClosedTradeIndex];
    console.log("Restoring trade:", trade.id, "Symbol:", trade.contractSymbol);

    // Revert balance changes
    ledger.balance -= (trade.grossPnl || 0);
    if (trade.exitCharges && trade.exitCharges.total) {
        ledger.balance += trade.exitCharges.total;
    }

    // Revert trade status and remove exit fields
    trade.status = "OPEN";
    delete trade.exitPrice;
    delete trade.exitReason;
    delete trade.mfe;
    delete trade.mae;
    delete trade.peakPrice;
    delete trade.troughPrice;
    delete trade.holdingDuration;
    delete trade.rMultiple;
    delete trade.holdingMode;
    delete trade.exitCharges;
    delete trade.grossPnl;
    delete trade.pnl;
    delete trade.netPnl;
    delete trade.returnPercent;
    delete trade.exitSlippage;
    delete trade.exitTimestamp;
    delete trade.endingBalance;
    delete trade.capitalDeployed;
    delete trade.concurrentPositions;

    // Save ledger
    fs.writeFileSync(ledgerPath, JSON.stringify(ledger, null, 2), "utf8");
    console.log("Trade restored successfully. New Balance:", ledger.balance);
} else {
    console.log("No closed trades found.");
}
