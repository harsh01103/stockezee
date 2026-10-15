// Swing Trading Screener: EMA Pullback & Volume Reclamation Strategy
// Target: Quick 5% to 8% gains on high-liquidity NSE stocks
// Uses direct Yahoo Finance v8 chart API (bypasses yahoo-finance2 library limitation)
import axios from 'axios';
import ti from 'technicalindicators';
import fs from 'fs';

const { EMA, BollingerBands } = ti;

// Load Nifty 200 / highly active stocks to prioritize
const PRIORITIZED_STOCKS = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL", "ITC", "LT", "BAJFINANCE",
    "MARUTI", "SUNPHARMA", "NTPC", "TATAMOTORS", "POWERGRID", "TITAN", "BAJAJFINSV", "HCLTECH", "WIPRO",
    "ONGC", "COALINDIA", "ADANIPORTS", "ULTRACEMCO", "NESTLEIND", "DRREDDY", "CIPLA", "DIVISLAB",
    "EICHERMOT", "HINDALCO", "JSWSTEEL", "TECHM", "HEROMOTOCO", "BPCL", "GRASIM", "TRENT", "ASIANPAINT",
    "AXISBANK", "KOTAKBANK", "HINDUNILVR", "TATASTEEL", "APOLLOHOSP", "ADANIENT",
    "SIEMENS", "HAL", "ABB", "ZOMATO", "JIOFIN", "VBL", "TATACONSUM", "DABUR", "MARICO", "GODREJCP",
    "PIDILITIND", "BIOCON", "BERGEPAINT", "HAVELLS", "VOLTAS", "JUBLFOOD", "PFC", "RECLTD", "NHPC",
    "INDIGO", "NAUKRI", "DMART", "COLPAL", "BOSCHLTD", "ACC", "AMBUJACEM", "SBICARD", "IRCTC", "PIIND",
    "CHOLAFIN", "SHRIRAMFIN", "MUTHOOTFIN", "BANKBARODA", "CANBK", "PNB", "IDFCFIRSTB", "FEDERALBNK",
    "SUZLON", "IREDA", "RVNL", "IRFC", "MAZDOCK", "COCHINSHIP", "HUDCO", "NBCC", "OLECTRA", "JSWINFRA",
    "ANGELONE", "CDSL", "BSE", "PAYTM", "PERSISTENT", "COFORGE", "LTTS", "MPHASIS", "POLYCAB", "DEEPAKNTR",
    "ASTRAL", "LALPATHLAB", "AUROPHARMA", "ALKEM", "TORNTPHARM", "TATAELXSI", "HAPPSTMNDS", "KPITTECH",
    "SJVN", "MANAPPURAM", "BANDHANBNK", "TATAPOWER", "BHEL", "BEL", "GAIL",
    "IOC", "SAIL", "HINDPETRO", "INDHOTEL", "PAGEIND", "ZYDUSLIFE", "GLENMARK", "LUPIN",
    "SUNTV", "CROMPTON", "CUMMINSIND", "BHARATFORG", "MRF", "BALKRISIND", "APOLLOTYRE", "EXIDEIND",
    "RBLBANK", "GMRAIRPORT", "JINDALSAW", "RATNAMANI",
    "TRIVENI", "GRINDWELL", "MASTEK", "TANLA", "ROUTE", "METROPOLIS", "SYNGENE", "NATCO",
    "GRANULES", "SUDARSCHEM", "FINEORG", "PRAJIND", "TIINDIA", "CEATLTD", "THERMAX",
    "KEC", "KALPATPOWR", "JKCEMENT", "RAMCOCEM", "DALBHARAT",
    "AFFLE", "LATENTVIEW", "INTELLECT", "BIRLASOFT", "ZENSAR", "DATAMATICS", "TATACOMM",
    "NAVINFLUOR", "AARTI", "ATUL", "CLEAN", "GNFC", "DEEPAKFERT", "CHAMBAL", "COROMANDEL", "UPL",
    "VGUARD", "KAJARIACER", "LAURUSLABS", "WELSPUNLIV", "RAYMOND", "TRIDENT",
    "RADICO", "EIDPARRY", "SHREECEM", "STARHEALTH", "SBILIFE", "HDFCLIFE",
    "MAXHEALTH", "FORTIS", "TATAPOWER", "TORNTPOWER",
    "IGL", "MGL", "TATACHEM", "SRF", "FLUOROCHEM",
    "ABCAPITAL", "AUBANK", "BATAINDIA", "BDL", "CANFINHOME", "ESCORTS",
    "HINDCOPPER", "IDEA", "INDIAMART", "INDUSTOWER", "LICHSGFIN",
    "NATIONALUM", "OBEROIRLTY", "PRESTIGE", "PVRINOX",
    "UBL", "VEDL", "MCX"
];

const PRIORITIZED_SET = new Set(PRIORITIZED_STOCKS);

// Helper
const last = (arr) => arr && arr.length > 0 ? arr[arr.length - 1] : null;

// -----------------------------------------------------------------
// Fetch chart data directly from Yahoo Finance v8 API
// -----------------------------------------------------------------
async function fetchChart(yfSymbol, days = 200) {
    const period1 = Math.floor((Date.now() - days * 86400000) / 1000);
    const period2 = Math.floor(Date.now() / 1000);
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(yfSymbol)}?period1=${period1}&period2=${period2}&interval=1d&includePrePost=false`;
    
    const resp = await axios.get(url, {
        headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
        },
        timeout: 12000,
    });

    const chart = resp.data?.chart?.result?.[0];
    if (!chart) return null;

    const timestamps = chart.timestamp;
    const q = chart.indicators?.quote?.[0];
    if (!timestamps || !q) return null;

    const quotes = [];
    for (let i = 0; i < timestamps.length; i++) {
        if (q.close[i] != null && q.open[i] != null && q.volume[i] != null) {
            quotes.push({
                date: new Date(timestamps[i] * 1000),
                open: q.open[i],
                high: q.high[i],
                low: q.low[i],
                close: q.close[i],
                volume: q.volume[i],
            });
        }
    }
    return quotes;
}

// -----------------------------------------------------------------
// 1. Scrape NSE equity list
// -----------------------------------------------------------------
async function getNSESymbols() {
    try {
        console.log('📡 Fetching official NSE equity list from archives.nseindia.com...');
        const response = await axios.get('https://archives.nseindia.com/content/equities/EQUITY_L.csv', {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/csv'
            },
            timeout: 10000
        });
        
        const lines = response.data.split('\n').filter(l => l.trim() !== '');
        const symbols = [];
        
        for (let i = 1; i < lines.length; i++) {
            const parts = lines[i].split(',');
            if (parts.length >= 2) {
                const sym = parts[0].trim();
                const name = parts[1].trim();
                const series = parts[2] ? parts[2].trim() : '';
                
                if (sym && sym !== 'SYMBOL' && (!series || series === 'EQ')) {
                    symbols.push({ symbol: sym, name: name });
                }
            }
        }
        console.log(`✅ Loaded ${symbols.length} NSE listed equities.`);
        return symbols;
    } catch (e) {
        console.warn('⚠️ Could not connect to archives.nseindia.com. Using fallback prioritized list.', e.message);
        return PRIORITIZED_STOCKS.map(s => ({ symbol: s, name: s }));
    }
}

// -----------------------------------------------------------------
// 2. Perform Technical Analysis Checks for 5-8% Swing Strategy
// -----------------------------------------------------------------
async function analyzeStock(stock) {
    const symbol = stock.symbol;
    const yfSymbol = `${symbol}.NS`;
    
    try {
        const quotes = await fetchChart(yfSymbol, 250);
        if (!quotes || quotes.length < 100) return null;
        
        const closes = quotes.map(q => q.close);
        const opens = quotes.map(q => q.open);
        const lows = quotes.map(q => q.low);
        const highs = quotes.map(q => q.high);
        const volumes = quotes.map(q => q.volume);
        
        const today = quotes[quotes.length - 1];
        const prev = quotes[quotes.length - 2];
        const prev2 = quotes[quotes.length - 3];
        
        // Skip penny and highly illiquid stocks
        if (today.close < 15) return null;
        const avgVol20 = volumes.slice(-21, -1).reduce((a, b) => a + b, 0) / 20;
        if (avgVol20 < 100000) return null;
        
        // Calculate EMAs
        const ema9Vals = EMA.calculate({ period: 9, values: closes });
        const ema21Vals = EMA.calculate({ period: 21, values: closes });
        const ema100Vals = EMA.calculate({ period: 100, values: closes });
        
        const ema9 = last(ema9Vals);
        const ema21 = last(ema21Vals);
        const ema100 = last(ema100Vals);
        
        if (!ema9 || !ema21 || !ema100) return null;
        
        // Calculate ATR percentage
        const trs = [];
        for (let i = quotes.length - 14; i < quotes.length; i++) {
            const h = quotes[i].high;
            const l = quotes[i].low;
            const pc = quotes[i-1] ? quotes[i-1].close : h;
            trs.push(Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc)));
        }
        const atr = trs.reduce((a, b) => a + b, 0) / 14;
        const atrPct = (atr / today.close) * 100;
        
        // Calculate Bollinger Bands
        const bbVals = BollingerBands.calculate({ period: 20, values: closes, stdDev: 2 });
        const bbToday = last(bbVals);
        
        // --- STRATEGY CRITERIA: The 9/21 EMA Pullback & Vol Reclaim ---
        
        // 1. Long term trend: Stock must be in an uptrend (price above 100 EMA)
        const isBullishTrend = today.close > ema100;
        
        // 2. Pullback: Stock has pulled back near the 21 EMA in the last 3 sessions
        const touchedEMA21 = (prev.low <= ema21Vals[ema21Vals.length - 2] * 1.02) || 
                             (prev2.low <= ema21Vals[ema21Vals.length - 3] * 1.02) ||
                             (today.low <= ema21 * 1.02);
                             
        // 3. Trigger Candle: Today's candle is bullish and holding/reclaiming above 9 EMA
        const isBullishToday = today.close > today.open;
        const reclaimsEMA9 = (today.close > ema9 && prev.close <= ema9Vals[ema9Vals.length - 2]) ||
                             (today.close > ema9 && today.low <= ema9 * 1.01);
        
        // 4. Volume Surge: Today's volume is active
        const volumeRatio = today.volume / avgVol20;
        const volumeSurge = volumeRatio > 1.1;

        // Pocket Pivot Check
        let maxDownVol = 0;
        for (let i = quotes.length - 11; i < quotes.length - 1; i++) {
            if (quotes[i].close < quotes[i].open) {
                maxDownVol = Math.max(maxDownVol, quotes[i].volume);
            }
        }
        const isPocketPivot = today.volume > maxDownVol && maxDownVol > 0;

        // Evaluate setup
        if (isBullishTrend && touchedEMA21 && isBullishToday && (reclaimsEMA9 || isPocketPivot)) {
            const targetPct = 6.5; 
            const target = today.close * (1 + targetPct / 100);
            
            const slLow = Math.min(today.low, prev.low, prev2.low);
            const stopLoss = slLow * 0.995;
            const slPct = ((today.close - stopLoss) / today.close) * 100;
            
            const rr = targetPct / Math.max(0.5, slPct);
            
            if (slPct < 6 && rr >= 1.3) {
                return {
                    symbol,
                    name: stock.name,
                    price: today.close,
                    change1d: ((today.close - prev.close) / prev.close) * 100,
                    volumeRatio,
                    atrPct,
                    isPocketPivot,
                    entry: today.close,
                    target: parseFloat(target.toFixed(2)),
                    targetPct,
                    stopLoss: parseFloat(stopLoss.toFixed(2)),
                    slPct: parseFloat(slPct.toFixed(1)),
                    riskReward: parseFloat(rr.toFixed(1)),
                    score: parseFloat((volumeRatio * 1.5 + (isPocketPivot ? 2 : 0) + (atrPct > 3 ? 1.5 : 0)).toFixed(1))
                };
            }
        }
    } catch (e) {
        // Silently skip — common for illiquid/delisted symbols
        if (!e.message?.includes('404') && !e.message?.includes('timeout')) {
            console.error(`Error for ${symbol}:`, e.message);
        }
    }
    return null;
}

// -----------------------------------------------------------------
// 3. Main Run
// -----------------------------------------------------------------
async function run() {
    console.log('🚀 === SWING SETUP SCANNER (5-8% Target Engine) ===');
    console.log('📊 Strategy: 9/21 EMA Pullback + Volume Reclamation');
    console.log('📈 Using direct Yahoo Finance v8 chart API\n');
    
    const nseSymbols = await getNSESymbols();
    
    // Sort symbols so prioritized high-liquidity stocks are scanned first
    const sortedSymbols = nseSymbols.sort((a, b) => {
        const aPri = PRIORITIZED_SET.has(a.symbol) ? 1 : 0;
        const bPri = PRIORITIZED_SET.has(b.symbol) ? 1 : 0;
        return bPri - aPri;
    });

    // Scan up to 200 top symbols to avoid API blockages
    const toScan = sortedSymbols.slice(0, 200);
    console.log(`🔍 Scanning ${toScan.length} liquid stocks for swing trading pullbacks...\n`);
    
    const results = [];
    const BATCH_SIZE = 10; // Smaller batches to avoid rate limiting
    let processed = 0;
    let errors = 0;
    
    for (let i = 0; i < toScan.length; i += BATCH_SIZE) {
        const batch = toScan.slice(i, i + BATCH_SIZE);
        const batchResults = await Promise.allSettled(batch.map(async (stock) => {
            const res = await analyzeStock(stock);
            if (res) results.push(res);
            return res;
        }));
        
        processed += batch.length;
        errors += batchResults.filter(r => r.status === 'rejected').length;
        
        // Progress indicator
        const pct = ((processed / toScan.length) * 100).toFixed(0);
        process.stdout.write(`\r   Progress: ${processed}/${toScan.length} (${pct}%) | Found: ${results.length} setups | Errors: ${errors}`);
        
        // Small delay between batches to respect rate limits
        if (i + BATCH_SIZE < toScan.length) {
            await new Promise(r => setTimeout(r, 300));
        }
    }
    
    console.log('\n');
    
    // Sort by setup score
    results.sort((a, b) => b.score - a.score);
    
    console.log('🌟 === TOP SWING CANDIDATES (5% - 8% TARGETS) === 🌟\n');
    if (results.length === 0) {
        console.log('❌ No high-probability swing pullbacks found right now.');
        console.log('   This is normal — not every day produces quality setups.');
        console.log('   Preservation of capital is key! 💎\n');
    } else {
        console.table(results.slice(0, 15).map(r => ({
            Symbol: r.symbol,
            Name: r.name?.slice(0, 20),
            Price: `₹${r.price.toFixed(2)}`,
            '1D Chg': `${r.change1d.toFixed(1)}%`,
            'Vol Ratio': `${r.volumeRatio.toFixed(1)}x`,
            'Pocket Pivot': r.isPocketPivot ? '✅ YES' : '—',
            Entry: `₹${r.entry.toFixed(2)}`,
            Target: `₹${r.target.toFixed(2)} (+${r.targetPct}%)`,
            SL: `₹${r.stopLoss.toFixed(2)} (-${r.slPct}%)`,
            'R:R': `1:${r.riskReward}`,
            Score: r.score
        })));
        
        // Write picks to a JSON file
        const output = {
            scan_date: new Date().toISOString(),
            strategy: 'EMA Pullback + Volume Reclamation',
            target_range: '5% - 8%',
            stocks_scanned: toScan.length,
            setups_found: results.length,
            top_picks: results.slice(0, 15),
        };
        
        fs.writeFileSync('swing_result.json', JSON.stringify(output, null, 4));
        console.log('\n💾 Wrote top swing picks to swing_result.json');
    }
}

run().catch(e => {
    console.error('💥 Fatal error:', e.message);
    process.exit(1);
});
