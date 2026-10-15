import { regimeEngine, REGIMES } from './regimeEngine.js';

async function runTests() {
    console.log('Testing Regime Engine...');

    const panicData = { vix: 40, atrExpansion: true, sp500Trend: 'DOWN' };
    const panicRegime = regimeEngine.classifyRegime(panicData);
    console.assert(panicRegime.regime === REGIMES.PANIC, 'Should classify as PANIC');
    console.assert(panicRegime.disabledStrategies.includes('VCP_BREAKOUT'), 'Should disable breakouts in panic');

    const bullTrendingData = { vix: 14, breadthPercent: 75, sp500Trend: 'UP' };
    const bullRegime = regimeEngine.classifyRegime(bullTrendingData);
    console.assert(bullRegime.regime === REGIMES.BULL_TRENDING, 'Should classify as BULL_TRENDING');
    console.assert(bullRegime.activeStrategies.includes('VCP_BREAKOUT'), 'Should enable VCP breakouts');

    const chopData = { vix: 18, breadthPercent: 50, sp500Trend: 'FLAT' };
    const chopRegime = regimeEngine.classifyRegime(chopData);
    console.assert(chopRegime.regime === REGIMES.CHOP_RANGE, 'Should classify as CHOP_RANGE');

    console.log('All Regime Engine tests passed!');
}

runTests().catch(console.error);
