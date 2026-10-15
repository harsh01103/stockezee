import { marketDisplay } from './marketDisplay.js';
import { marketDecision } from './marketDecision.js';
import { marketExecution } from './marketExecution.js';

// Mock fallback service
const mockService = async (key, options) => {
    return {
        instrument_key: key,
        last_price: 100,
        volume: 5000
    };
};

async function runTests() {
    console.log('Testing Market Streams...');

    // 1. Display
    const disp = await marketDisplay.getQuote('NIFTY', mockService);
    console.assert(disp.stream === 'DISPLAY', 'Display stream failed');
    console.assert(disp.last_price === 100, 'Display price failed');

    // 2. Decision
    const dec = await marketDecision.getQuote('NIFTY', mockService);
    console.assert(dec.stream === 'DECISION', 'Decision stream failed');
    console.assert(dec.reliability === 'HIGH', 'Decision reliability failed');

    // 3. Execution
    const exec = await marketExecution.getQuote('NIFTY', mockService);
    console.assert(exec.stream === 'EXECUTION', 'Execution stream failed');
    console.assert(exec.confirmed === true, 'Execution confirmed failed');

    console.log('All Market Stream tests passed!');
}

runTests().catch(console.error);
