const https = require('https');
const fs = require('fs');

https.get('https://archives.nseindia.com/content/equities/EQUITY_L.csv', { headers: { 'User-Agent': 'Mozilla/5.0' } }, (res) => {
    let data = '';
    res.on('data', c => data += c);
    res.on('end', () => {
        let lines = data.split('\n').filter(l => l.trim() !== '');
        let results = [];
        for (let i = 1; i < lines.length; i++) {
            let parts = lines[i].split(',');
            if (parts.length >= 2) {
                let sym = parts[0].trim();
                let name = parts[1].trim();
                if (sym && !sym.includes(' ') && sym !== 'SYMBOL') {
                    results.push({ symbol: sym, name: name });
                }
            }
        }
        fs.writeFileSync('api/symbols.json', JSON.stringify(results));
        console.log('Successfully wrote ' + results.length + ' symbols to api/symbols.json');
    });
});
