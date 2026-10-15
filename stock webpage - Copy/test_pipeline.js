import { DataAcquisitionManager } from './server/services/ingestion/providerInterface.js';
import { YahooFinanceProvider } from './server/services/ingestion/providers/yahooFinanceProvider.js';
import { FeatureEngine } from './server/services/compute/featureEngine.js';
import { PatternEngine } from './server/services/compute/patternEngine.js';

async function testPipeline() {
    console.log("=== 1. Testing Data Acquisition ===");
    const manager = new DataAcquisitionManager();
    manager.registerProvider(new YahooFinanceProvider());
    
    const endDate = new Date();
    const startDate = new Date();
    startDate.setFullYear(endDate.getFullYear() - 1); // Test 1 year for speed

    let ohlcv = [];
    try {
        ohlcv = await manager.fetchHistoricalOHLCV('RELIANCE', startDate, endDate);
        console.log(`Success: Fetched ${ohlcv.length} days of data for RELIANCE.`);
        if (ohlcv.length > 0) {
            console.log("Sample:", ohlcv[0]);
        }
    } catch (e) {
        console.error("Failed to fetch OHLCV:", e.message);
    }

    if (ohlcv.length === 0) return;

    console.log("\n=== 2. Testing Feature Engine ===");
    const closes = ohlcv.map(q => q.close);
    const sma50 = FeatureEngine.computeSMA(closes, 50);
    console.log(`SMA(50) of RELIANCE: ${sma50}`);

    console.log("\n=== 3. Testing Pattern Engine (VCP) ===");
    const vcpResult = PatternEngine.detectVCP(ohlcv);
    console.log("VCP Detection:", vcpResult);
}

testPipeline().then(() => console.log("Done")).catch(console.error);
