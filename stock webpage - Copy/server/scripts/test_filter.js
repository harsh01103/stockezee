import axios from 'axios';
import zlib from 'zlib';
import csv from 'csv-parser';
import { Readable } from 'stream';

async function testFilter(exchange) {
    console.log(`Fetching ${exchange}...`);
    const res = await axios.get(`https://assets.upstox.com/market-quote/instruments/exchange/${exchange}.csv.gz`, { responseType: 'arraybuffer' });
    const stream = Readable.from(zlib.gunzipSync(res.data));
    
    let total = 0;
    let allowed = 0;
    let allowedSamples = [];
    
    stream.pipe(csv()).on('data', (d) => {
        total++;
        const type = d.instrument_type || '';
        const series = d.series || '';
        const name = d.name || '';
        const symbol = d.tradingsymbol || '';
        
        const isEquityType = type === 'EQUITY';
        const isAllowedSeries = series === 'EQ' || series === 'BE' || series === '';
        const isEtf = type === 'ETF' || name.includes('ETF') || name.includes('BEES') || (series === 'EQ' && name.includes('NIFTY'));
        const rejectTypes = ['BOND', 'NCD', 'GB', 'SG', 'MF', 'FUT', 'OPT', 'PREF', 'WARRANT', 'DEBT', 'COMMODITY', 'INDEX', 'CURRENCY', 'GS'];
        const isRejected = rejectTypes.includes(type) || rejectTypes.some(t => name.toUpperCase().includes(t + ' ') || name.toUpperCase().includes(' ' + t));

        if (!isRejected && (isEquityType || isEtf) && isAllowedSeries) {
            allowed++;
            if (allowed < 50 || symbol.includes('GS') || name.includes('BOND') || name.includes('DEBT')) {
                allowedSamples.push({symbol, name, type, series, isEtf, isEquityType, isRejected});
            }
        }
    }).on('end', () => {
        console.log(`${exchange}: Total=${total}, Allowed=${allowed}`);
        console.log("Samples of allowed that look suspicious:");
        console.table(allowedSamples.filter(s => s.symbol.match(/^[0-9]+[A-Z]+[0-9]+/) || s.symbol.length > 10).slice(0, 20));
    });
}

testFilter('NSE');
testFilter('BSE');
