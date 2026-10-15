import yahooFinance from 'yahoo-finance2';
async function run() {
    const r = await yahooFinance.chart('RELIANCE.NS', { interval: '1m', range: '5d' });
    const q = r.quotes;
    console.log("Length:", q.length);
    if (q.length > 0) {
        console.log("First:", new Date(q[0].date).toLocaleString());
        console.log("Last:", new Date(q[q.length - 1].date).toLocaleString());
    }
}
run();
