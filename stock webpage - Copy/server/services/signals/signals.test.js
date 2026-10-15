import { signalEngine } from './signalEngine.js';
import { signalLogger } from './signalLogger.js';
import { signalReplay } from './signalReplay.js';

async function runTests() {
    console.log('Testing Signal Registry...');

    const mockMarketData = {
        ltp: 150.50,
        momentum: 0.9,
        vcpConfirmed: true,
        rsi: 65
    };

    // 1. Engine & Logger
    const signals = await signalEngine.evaluate('RELIANCE', mockMarketData);
    console.assert(signals.length > 0, 'Signal engine should generate signals');

    const recent = await signalLogger.getRecentSignals();
    console.assert(recent.length > 0, 'Signal logger should persist signals');

    // 2. Replay
    const outcomes = await signalReplay.evaluateOutcomes('RELIANCE', 5);
    console.assert(outcomes.length > 0, 'Signal replay should evaluate outcomes');

    console.log('All Signal Registry tests passed!');
}

runTests().catch(console.error);
