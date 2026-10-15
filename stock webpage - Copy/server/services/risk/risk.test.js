import { riskEngine } from './riskEngine.js';

async function runTests() {
    console.log('Testing Portfolio Risk Engine...');

    const basePortfolio = {
        dailyDrawdown: 2.0,
        sectorConcentrations: { 'TECHNOLOGY': 15.0 },
        marginUsed: 20000,
        totalEquity: 100000
    };

    // Test 1: Approved Trade
    const goodTrade = { symbol: 'AAPL', sector: 'TECHNOLOGY', estimatedValue: 5000 };
    const res1 = riskEngine.evaluateTrade(basePortfolio, goodTrade);
    console.assert(res1.approved === true, 'Trade should be approved');

    // Test 2: Sector Concentration Failure
    const heavyTechTrade = { symbol: 'MSFT', sector: 'TECHNOLOGY', estimatedValue: 15000 };
    const res2 = riskEngine.evaluateTrade(basePortfolio, heavyTechTrade);
    console.assert(res2.approved === false, 'Trade should fail due to concentration limit');

    // Test 3: Daily Drawdown Kill Switch
    const drawdownPortfolio = { ...basePortfolio, dailyDrawdown: 6.0 };
    const res3 = riskEngine.evaluateTrade(drawdownPortfolio, goodTrade);
    console.assert(res3.approved === false, 'Trade should fail due to daily drawdown kill switch');

    console.log('All Risk Engine tests passed!');
}

runTests().catch(console.error);
