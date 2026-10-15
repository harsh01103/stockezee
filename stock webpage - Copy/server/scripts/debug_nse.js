import axios from 'axios';
import zlib from 'zlib';
import csv from 'csv-parser';
import { Readable } from 'stream';

async function debugNSE() {
    const res = await axios.get(`https://assets.upstox.com/market-quote/instruments/exchange/NSE.csv.gz`, { responseType: 'arraybuffer' });
    const stream = Readable.from(zlib.gunzipSync(res.data));
    
    const seriesCounts = {};
    let reliance = null;
    let gsExample = null;
    let total = 0;
    
    stream.pipe(csv()).on('data', (d) => {
        total++;
        const type = d.instrument_type || '';
        const series = d.series || '';
        
        if (type === 'EQUITY') {
            seriesCounts[series] = (seriesCounts[series] || 0) + 1;
        }
        
        if (d.tradingsymbol === 'RELIANCE') {
            reliance = { symbol: d.tradingsymbol, name: d.name, type, series, exchange: d.exchange };
        }
        if (d.tradingsymbol === 'GS16DEC2030') {
            gsExample = { symbol: d.tradingsymbol, name: d.name, type, series, exchange: d.exchange };
        }
    }).on('end', () => {
        console.log(`NSE Total rows: ${total}`);
        console.log('Series distribution for EQUITY type:');
        console.log(seriesCounts);
        console.log('\nRELIANCE:', reliance);
        console.log('GS16DEC2030:', gsExample);
    });
}

debugNSE();
