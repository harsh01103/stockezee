import axios from 'axios';
import zlib from 'zlib';
import csv from 'csv-parser';
import { Readable } from 'stream';

async function testEquities() {
    console.log(`Fetching BSE...`);
    const res = await axios.get(`https://assets.upstox.com/market-quote/instruments/exchange/BSE.csv.gz`, { responseType: 'arraybuffer' });
    const stream = Readable.from(zlib.gunzipSync(res.data));
    
    stream.pipe(csv()).on('data', (d) => {
        if (d.name === 'RELIANCE INDUSTRIES LTD' || d.tradingsymbol === 'RELIANCE' || d.tradingsymbol === 'SBIN') {
            console.log(d);
        }
    }).on('end', () => console.log('Done'));
}

testEquities();
