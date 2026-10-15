import yahooFinance from 'yahoo-finance2';

async function main() {
    const sym = 'RELIANCE';
    const hist = await yahooFinance.chart(sym + '.NS', { period1: new Date(Date.now() - 400 * 86400000).toISOString(), interval: '1d' });
    const q = hist.quotes.filter(q => q.volume != null && q.close != null && q.open != null);
    const today = q[q.length - 1];
    const volumes = q.map(q => q.volume);
    const avgVol20 = volumes.slice(-21, -1).reduce((a, b) => a + b, 0) / 20;
    const turnover = today.close * avgVol20;

    console.log('total quotes:', q.length);
    console.log('today.close:', today.close);
    console.log('avgVol20:', avgVol20);
    console.log('turnover:', turnover);
}
main().catch(console.error);
