import YahooFinance from 'yahoo-finance2';
import ti from 'technicalindicators';
import { runProScreener } from './mlScreener.js';

// Must instantiate exactly like server/index.js does:
const yahooFinance = new YahooFinance();

async function main() {
    const res = await runProScreener('swing', yahooFinance, ti, [], null, null);
    console.log('Swing setup count:', res.results.length);
    console.log('Universe scanned:', res.universe_scanned);
    if (res.results.length > 0) {
        console.log('First result:', JSON.stringify(res.results[0], null, 2));
    }
}
main().catch(console.error);
