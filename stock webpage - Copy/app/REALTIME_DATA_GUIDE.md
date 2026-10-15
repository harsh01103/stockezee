# Real-Time Market Data Integration Guide

This guide explains how to connect real-time market data to your trading platform and make the demo page fully live.

---

## Table of Contents

1. [Overview](#overview)
2. [Free Data Providers](#free-data-providers)
3. [Implementation Steps](#implementation-steps)
4. [Code Integration](#code-integration)
5. [Making the Page Live](#making-the-page-live)
6. [Troubleshooting](#troubleshooting)

---

## Overview

The DemoPage uses **lightweight-charts** for rendering professional candlestick charts. To make it live with real data, you need to:

1. Connect to a WebSocket or REST API for market data
2. Update the chart with incoming price updates
3. Handle trade execution with real prices

---

## Free Data Providers

### 1. Binance (Best for Crypto - FREE)
- **Coverage**: 1000+ cryptocurrency pairs
- **Cost**: FREE, no API key required
- **WebSocket**: Yes, real-time
- **Rate Limits**: None for WebSocket
- **Documentation**: https://binance-docs.github.io/apidocs/spot/en/#websocket-market-streams

### 2. Finnhub (Best for Stocks - FREE Tier)
- **Coverage**: US stocks, forex, crypto
- **Cost**: Free tier available (60 calls/min)
- **WebSocket**: Yes
- **Sign up**: https://finnhub.io/
- **Documentation**: https://finnhub.io/docs/api

### 3. Alpha Vantage (Good for Historical Data)
- **Coverage**: Stocks, forex, crypto
- **Cost**: Free tier (25 calls/day)
- **WebSocket**: No (REST API only)
- **Sign up**: https://www.alphavantage.co/support/#api-key

### 4. Polygon.io (Good for US Markets)
- **Coverage**: US stocks, options
- **Cost**: Free tier (5 calls/min, delayed data)
- **Sign up**: https://polygon.io/

---

## Implementation Steps

### Step 1: Get API Keys (Optional but Recommended)

For extended functionality beyond crypto, sign up for:

1. **Finnhub** (for stocks and forex):
   ```
   1. Go to https://finnhub.io/
   2. Click "Get Free API Key"
   3. Copy your API key
   ```

2. **Alpha Vantage** (for historical data):
   ```
   1. Go to https://www.alphavantage.co/support/#api-key
   2. Request a free API key
   ```

### Step 2: Update DemoPage.tsx

Replace the simulated data with real WebSocket connections:

```typescript
import { MarketDataService } from '@/services/websocketService';

// Inside your component:
const marketData = useRef<MarketDataService | null>(null);

useEffect(() => {
  // Initialize market data service
  marketData.current = new MarketDataService({
    // Add your API keys here (optional for crypto)
    finnhubApiKey: 'YOUR_FINNHUB_API_KEY', // Optional
    
    // Handle price updates
    onPriceUpdate: (symbol, price) => {
      setCurrentPrice(price);
      
      // Update chart
      if (seriesRef.current) {
        const lastCandle = seriesRef.current.data()[seriesRef.current.data().length - 1];
        if (lastCandle) {
          seriesRef.current.update({
            time: lastCandle.time,
            open: lastCandle.open,
            high: Math.max(lastCandle.high, price),
            low: Math.min(lastCandle.low, price),
            close: price,
          });
        }
      }
    },
    
    // Handle candle updates
    onCandleUpdate: (symbol, candle) => {
      if (seriesRef.current) {
        seriesRef.current.update(candle);
      }
    },
  });

  // Connect to WebSocket
  marketData.current.connect();

  // Subscribe to selected asset
  const assetType = selectedAsset.category === 'crypto' ? 'crypto' : 
                    selectedAsset.category === 'stocks' ? 'stock' : 'forex';
  marketData.current.subscribe(selectedAsset.symbol, assetType);

  return () => {
    marketData.current?.disconnect();
  };
}, [selectedAsset]);
```

### Step 3: Fetch Historical Data

For initial chart data, use REST APIs:

```typescript
// Add to useEffect when asset changes
const fetchHistoricalData = async () => {
  try {
    // For crypto - use Binance REST API
    const response = await fetch(
      `https://api.binance.com/api/v3/klines?symbol=${selectedAsset.symbol.replace('/', '')}&interval=1m&limit=100`
    );
    const data = await response.json();
    
    // Convert to lightweight-charts format
    const candles = data.map((kline: any) => ({
      time: kline[0] / 1000,
      open: parseFloat(kline[1]),
      high: parseFloat(kline[2]),
      low: parseFloat(kline[3]),
      close: parseFloat(kline[4]),
    }));
    
    seriesRef.current?.setData(candles);
  } catch (error) {
    console.error('Failed to fetch historical data:', error);
  }
};

fetchHistoricalData();
```

---

## Code Integration

### Full Integration Example

Here's the complete integration for the DemoPage:

```typescript
// At the top of DemoPage.tsx
import { MarketDataService } from '@/services/websocketService';

// Replace the simulated price update useEffect with:
useEffect(() => {
  // Initialize market data service
  marketData.current = new MarketDataService({
    finnhubApiKey: import.meta.env.VITE_FINNHUB_API_KEY, // From .env file
    
    onPriceUpdate: (symbol, price) => {
      if (symbol === selectedAsset.symbol) {
        setCurrentPrice(price);
        
        // Update chart with new price
        if (seriesRef.current) {
          const data = seriesRef.current.data();
          const lastCandle = data[data.length - 1];
          if (lastCandle) {
            seriesRef.current.update({
              time: lastCandle.time,
              open: lastCandle.open,
              high: Math.max(lastCandle.high, price),
              low: Math.min(lastCandle.low, price),
              close: price,
            });
          }
        }
      }
    },
    
    onCandleUpdate: (symbol, candle) => {
      if (symbol === selectedAsset.symbol && seriesRef.current) {
        seriesRef.current.update(candle);
      }
    },
  });

  marketData.current.connect();

  // Determine asset type and subscribe
  const assetType = selectedAsset.category === 'crypto' ? 'crypto' : 
                    selectedAsset.category === 'stocks' ? 'stock' : 'forex';
  
  marketData.current.subscribe(selectedAsset.symbol, assetType);

  // Fetch initial historical data
  const fetchHistory = async () => {
    try {
      let url;
      if (selectedAsset.category === 'crypto') {
        const symbol = selectedAsset.symbol.replace('/', '');
        url = `https://api.binance.com/api/v3/klines?symbol=${symbol}&interval=1m&limit=100`;
        const response = await fetch(url);
        const data = await response.json();
        const candles = data.map((k: any[]) => ({
          time: k[0] / 1000,
          open: parseFloat(k[1]),
          high: parseFloat(k[2]),
          low: parseFloat(k[3]),
          close: parseFloat(k[4]),
        }));
        seriesRef.current?.setData(candles);
      }
    } catch (error) {
      console.error('Error fetching historical data:', error);
    }
  };

  fetchHistory();

  return () => {
    marketData.current?.disconnect();
  };
}, [selectedAsset]);
```

### Environment Variables

Create a `.env` file in your project root:

```bash
# .env
VITE_FINNHUB_API_KEY=your_finnhub_api_key_here
VITE_ALPHAVANTAGE_API_KEY=your_alphavantage_api_key_here
VITE_POLYGON_API_KEY=your_polygon_api_key_here
```

---

## Making the Page Live

### Option 1: Deploy to Vercel (Recommended)

1. **Install Vercel CLI**:
   ```bash
   npm i -g vercel
   ```

2. **Deploy**:
   ```bash
   cd /mnt/okcomputer/output/app
   vercel --prod
   ```

3. **Add Environment Variables**:
   - Go to Vercel Dashboard
   - Select your project
   - Go to Settings → Environment Variables
   - Add your API keys

### Option 2: Deploy to Netlify

1. **Build the project**:
   ```bash
   cd /mnt/okcomputer/output/app
   npm run build
   ```

2. **Deploy dist folder** to Netlify

3. **Add Environment Variables** in Netlify Dashboard

### Option 3: Deploy to GitHub Pages

1. **Push to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Enable GitHub Pages** in repository settings

---

## Troubleshooting

### Issue: WebSocket not connecting

**Solution**:
- Check if you're behind a firewall
- Verify the WebSocket URL is correct
- Check browser console for errors

### Issue: No data showing on chart

**Solution**:
- Verify the symbol format (BTC/USD vs BTCUSDT)
- Check if the API is returning data
- Ensure the chart is properly initialized

### Issue: CORS errors

**Solution**:
- Use a CORS proxy for development
- For production, ensure your API supports CORS
- Consider using a backend server as a proxy

### Issue: Rate limit exceeded

**Solution**:
- Implement request caching
- Add delays between requests
- Upgrade to a paid plan

---

## Additional Features to Add

### 1. Technical Indicators

```typescript
// Add moving average
const maSeries = chart.addLineSeries({
  color: '#f59e0b',
  lineWidth: 2,
});

// Calculate and set MA data
const maData = calculateMA(candleData, 20);
maSeries.setData(maData);
```

### 2. Drawing Tools

```typescript
// Add price lines
const buyLine = series.createPriceLine({
  price: entryPrice,
  color: '#22c55e',
  lineWidth: 2,
  title: 'Entry',
});
```

### 3. Order Book

```typescript
// Fetch order book from Binance
const fetchOrderBook = async () => {
  const response = await fetch(
    `https://api.binance.com/api/v3/depth?symbol=${symbol}&limit=20`
  );
  const data = await response.json();
  // Display bids and asks
};
```

---

## Security Considerations

1. **Never expose API keys in client-side code**
   - Use environment variables
   - Consider a backend proxy

2. **Implement rate limiting**
   - Cache data when possible
   - Don't make unnecessary requests

3. **Validate all data**
   - Check for null/undefined values
   - Handle API errors gracefully

---

## Summary

To make your trading platform live:

1. ✅ Get free API keys from Finnhub/Alpha Vantage
2. ✅ Integrate WebSocket service (already created in `websocketService.ts`)
3. ✅ Replace simulated data with real market data
4. ✅ Deploy to Vercel/Netlify with environment variables
5. ✅ Test with different assets and timeframes

The platform is now ready for real-time trading with live market data!
