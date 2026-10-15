import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
import { FeatureEngine } from './services/compute/featureEngine.js';
import YahooFinance from 'yahoo-finance2';

dotenv.config({ path: '../.env' });
const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE);
const yahooFinance = new YahooFinance();

async function test() {
    const symbol = 'AEGISLOG';
    const { data: ohlcv } = await supabase
        .from('daily_ohlcv')
        .select('date, open, high, low, close, volume, traded_value')
        .eq('symbol', symbol)
        .order('date', { ascending: true })
        .limit(500);

    const closes = ohlcv.map(d => d.close);
    console.log("Length:", closes.length);
    const currentPrice = closes[closes.length - 1];
    console.log("Price:", currentPrice);

    const stage2 = FeatureEngine.checkWeinsteinStage2(closes);
    console.log("Stage 2:", stage2.isStage2);

    const endDate = new Date();
    const startDate = new Date();
    startDate.setFullYear(endDate.getFullYear() - 2);
    const niftyDataRaw = await yahooFinance.historical('^NSEI', { period1: startDate, period2: endDate, interval: '1d' }).catch(() => []);
    const niftyPrices = niftyDataRaw.map(d => d.close);

    const rs3m = FeatureEngine.computeRelativeStrength(closes, niftyPrices, 66);
    console.log("RS 3M:", rs3m);

    const rsi = FeatureEngine.computeRSI(closes, 14);
    console.log("RSI:", rsi);

    const isOBVRising = FeatureEngine.isOBVRising(ohlcv, 20);
    console.log("OBV Rising:", isOBVRising);
}

test().then(() => process.exit(0));
