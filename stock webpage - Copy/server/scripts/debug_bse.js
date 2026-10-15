import axios from 'axios';
import zlib from 'zlib';
import csv from 'csv-parser';
import { Readable } from 'stream';

async function debugBSE() {
    const res = await axios.get(`https://assets.upstox.com/market-quote/instruments/exchange/BSE.csv.gz`, { responseType: 'arraybuffer' });
    const stream = Readable.from(zlib.gunzipSync(res.data));
    
    const seriesCounts = {};
    let gsExample = null;
    let pfcl = [];
    let total = 0;
    
    stream.pipe(csv()).on('data', (d) => {
        total++;
        const type = d.instrument_type || '';
        const series = d.series || '';
        
        if (type === 'EQUITY') {
            seriesCounts[series] = (seriesCounts[series] || 0) + 1;
        }
        
        if ((d.tradingsymbol || '').includes('GS16')) {
            gsExample = { symbol: d.tradingsymbol, name: d.name, type, series, exchange: d.exchange };
        }
        if ((d.tradingsymbol || '').startsWith('PFCL')) {
            pfcl.push({ symbol: d.tradingsymbol, name: d.name, type, series, exchange: d.exchange });
        }
    }).on('end', () => {
        console.log(`BSE Total rows: ${total}`);
        console.log('Series distribution for EQUITY type:');
        console.log(seriesCounts);
        console.log('\nGS16*:', gsExample);
        console.log('\nPFCL entries:');
        pfcl.forEach(p => console.log(p));
    });
}

debugBSE();
