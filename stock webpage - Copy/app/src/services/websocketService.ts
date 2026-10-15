/**
 * WebSocket Service for Real-Time Market Data
 * 
 * This service provides a unified interface for connecting to various
 * real-time market data providers. It handles connection management,
 * message parsing, and data normalization.
 */

// ============================================
// OPTION 1: Binance WebSocket (Free - Crypto Only)
// ============================================
// Binance provides free WebSocket streams for cryptocurrency data
// Documentation: https://binance-docs.github.io/apidocs/spot/en/#websocket-market-streams

export class BinanceWebSocketService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 3000;
  private subscriptions: Set<string> = new Set();
  private onPriceUpdate: ((symbol: string, price: number) => void) | null = null;
  private onCandleUpdate: ((symbol: string, candle: any) => void) | null = null;

  constructor(
    onPriceUpdate?: (symbol: string, price: number) => void,
    onCandleUpdate?: (symbol: string, candle: any) => void
  ) {
    this.onPriceUpdate = onPriceUpdate || null;
    this.onCandleUpdate = onCandleUpdate || null;
  }

  connect() {
    // Binance WebSocket endpoint
    const wsUrl = 'wss://stream.binance.com:9443/ws';
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('Binance WebSocket connected');
      this.reconnectAttempts = 0;
      
      // Resubscribe to all previous subscriptions
      this.subscriptions.forEach(symbol => this.subscribe(symbol));
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      // Handle different message types
      if (data.e === 'trade') {
        // Real-time trade data
        const symbol = data.s; // Symbol (e.g., BTCUSDT)
        const price = parseFloat(data.p); // Price
        if (this.onPriceUpdate) {
          this.onPriceUpdate(symbol, price);
        }
      } else if (data.e === 'kline') {
        // Candlestick data
        const symbol = data.s;
        const kline = data.k;
        const candle = {
          time: kline.t / 1000, // Timestamp in seconds
          open: parseFloat(kline.o),
          high: parseFloat(kline.h),
          low: parseFloat(kline.l),
          close: parseFloat(kline.c),
          volume: parseFloat(kline.v),
        };
        if (this.onCandleUpdate) {
          this.onCandleUpdate(symbol, candle);
        }
      }
    };

    this.ws.onerror = (error) => {
      console.error('Binance WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('Binance WebSocket disconnected');
      this.attemptReconnect();
    };
  }

  subscribe(symbol: string, interval: string = '1m') {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.subscriptions.add(symbol);
      return;
    }

    // Convert symbol format (BTC/USD -> btcusdt)
    const formattedSymbol = symbol.toLowerCase().replace('/', '');
    
    // Subscribe to trade stream
    const tradeSubscription = {
      method: 'SUBSCRIBE',
      params: [`${formattedSymbol}@trade`],
      id: Date.now(),
    };
    
    // Subscribe to kline (candlestick) stream
    const klineSubscription = {
      method: 'SUBSCRIBE',
      params: [`${formattedSymbol}@kline_${interval}`],
      id: Date.now() + 1,
    };

    this.ws.send(JSON.stringify(tradeSubscription));
    this.ws.send(JSON.stringify(klineSubscription));
    this.subscriptions.add(symbol);
  }

  unsubscribe(symbol: string) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    const formattedSymbol = symbol.toLowerCase().replace('/', '');
    const unsubscription = {
      method: 'UNSUBSCRIBE',
      params: [`${formattedSymbol}@trade`, `${formattedSymbol}@kline_1m`],
      id: Date.now(),
    };

    this.ws.send(JSON.stringify(unsubscription));
    this.subscriptions.delete(symbol);
  }

  private attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
      setTimeout(() => this.connect(), this.reconnectDelay);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// ============================================
// OPTION 2: Finnhub WebSocket (Free - Stocks & Forex)
// ============================================
// Finnhub provides free real-time data for stocks and forex
// Sign up at: https://finnhub.io/
// Free tier: 60 API calls/minute, WebSocket access

export class FinnhubWebSocketService {
  private ws: WebSocket | null = null;
  private apiKey: string;
  private onPriceUpdate: ((symbol: string, price: number) => void) | null = null;

  constructor(apiKey: string, onPriceUpdate?: (symbol: string, price: number) => void) {
    this.apiKey = apiKey;
    this.onPriceUpdate = onPriceUpdate || null;
  }

  connect() {
    const wsUrl = `wss://ws.finnhub.io?token=${this.apiKey}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('Finnhub WebSocket connected');
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'trade' && data.data) {
        data.data.forEach((trade: any) => {
          if (this.onPriceUpdate) {
            this.onPriceUpdate(trade.s, trade.p);
          }
        });
      }
    };

    this.ws.onerror = (error) => {
      console.error('Finnhub WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('Finnhub WebSocket disconnected');
    };
  }

  subscribe(symbol: string) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    const subscription = { type: 'subscribe', symbol };
    this.ws.send(JSON.stringify(subscription));
  }

  unsubscribe(symbol: string) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    const unsubscription = { type: 'unsubscribe', symbol };
    this.ws.send(JSON.stringify(unsubscription));
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// ============================================
// OPTION 3: Alpha Vantage (Free Tier - REST API)
// ============================================
// Alpha Vantage provides free stock and forex data via REST API
// Sign up at: https://www.alphavantage.co/support/#api-key
// Free tier: 25 API calls/day

export class AlphaVantageService {
  private apiKey: string;
  private baseUrl = 'https://www.alphavantage.co/query';

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  async getIntradayData(symbol: string, interval: '1min' | '5min' | '15min' | '30min' | '60min' = '1min') {
    const params = new URLSearchParams({
      function: 'TIME_SERIES_INTRADAY',
      symbol,
      interval,
      apikey: this.apiKey,
    });

    const response = await fetch(`${this.baseUrl}?${params}`);
    const data = await response.json();
    return data;
  }

  async getForexData(fromCurrency: string, toCurrency: string, interval: string = '1min') {
    const params = new URLSearchParams({
      function: 'FX_INTRADAY',
      from_symbol: fromCurrency,
      to_symbol: toCurrency,
      interval,
      apikey: this.apiKey,
    });

    const response = await fetch(`${this.baseUrl}?${params}`);
    const data = await response.json();
    return data;
  }

  async getCryptoData(symbol: string, market: string = 'USD') {
    const params = new URLSearchParams({
      function: 'DIGITAL_CURRENCY_INTRADAY',
      symbol,
      market,
      apikey: this.apiKey,
    });

    const response = await fetch(`${this.baseUrl}?${params}`);
    const data = await response.json();
    return data;
  }
}

// ============================================
// OPTION 4: Polygon.io (Free Tier - US Stocks)
// ============================================
// Polygon.io provides real-time and historical market data
// Sign up at: https://polygon.io/
// Free tier: 5 API calls/minute, delayed data

export class PolygonService {
  private apiKey: string;
  private baseUrl = 'https://api.polygon.io/v2';

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  async getAggregates(symbol: string, multiplier: number = 1, timespan: string = 'minute', from: string, to: string) {
    const url = `${this.baseUrl}/aggs/ticker/${symbol}/range/${multiplier}/${timespan}/${from}/${to}?apiKey=${this.apiKey}`;
    const response = await fetch(url);
    const data = await response.json();
    return data;
  }

  async getLastTrade(symbol: string) {
    const url = `${this.baseUrl}/last/trade/${symbol}?apiKey=${this.apiKey}`;
    const response = await fetch(url);
    const data = await response.json();
    return data;
  }
}

// ============================================
// UNIFIED MARKET DATA SERVICE
// ============================================
// This class combines multiple providers for comprehensive coverage

export class MarketDataService {
  private binance: BinanceWebSocketService | null = null;
  private finnhub: FinnhubWebSocketService | null = null;

  constructor(config: {
    finnhubApiKey?: string;
    alphaVantageApiKey?: string;
    polygonApiKey?: string;
    onPriceUpdate?: (symbol: string, price: number) => void;
    onCandleUpdate?: (symbol: string, candle: any) => void;
  }) {
    // Initialize Binance (always available for crypto)
    this.binance = new BinanceWebSocketService(config.onPriceUpdate, config.onCandleUpdate);

    // Initialize Finnhub if API key provided (for stocks and forex)
    if (config.finnhubApiKey) {
      this.finnhub = new FinnhubWebSocketService(config.finnhubApiKey, config.onPriceUpdate);
    }
    
    // Note: Alpha Vantage and Polygon can be initialized separately when needed
    // using their respective service classes for REST API calls:
    // const alphaVantage = new AlphaVantageService(config.alphaVantageApiKey);
    // const polygon = new PolygonService(config.polygonApiKey);
  }

  connect() {
    this.binance?.connect();
    this.finnhub?.connect();
  }

  subscribe(symbol: string, assetType: 'crypto' | 'stock' | 'forex' = 'crypto') {
    switch (assetType) {
      case 'crypto':
        this.binance?.subscribe(symbol);
        break;
      case 'stock':
        this.finnhub?.subscribe(symbol);
        break;
      case 'forex':
        this.finnhub?.subscribe(`OANDA:${symbol}`);
        break;
    }
  }

  unsubscribe(symbol: string, assetType: 'crypto' | 'stock' | 'forex' = 'crypto') {
    switch (assetType) {
      case 'crypto':
        this.binance?.unsubscribe(symbol);
        break;
      case 'stock':
        this.finnhub?.unsubscribe(symbol);
        break;
      case 'forex':
        this.finnhub?.unsubscribe(`OANDA:${symbol}`);
        break;
    }
  }

  disconnect() {
    this.binance?.disconnect();
    this.finnhub?.disconnect();
  }
}

// ============================================
// USAGE EXAMPLE
// ============================================

/*
// In your React component:

import { MarketDataService } from './services/websocketService';

const marketData = new MarketDataService({
  // Optional: Add your API keys for extended functionality
  finnhubApiKey: 'YOUR_FINNHUB_API_KEY',
  alphaVantageApiKey: 'YOUR_ALPHAVANTAGE_API_KEY',
  polygonApiKey: 'YOUR_POLYGON_API_KEY',
  
  // Callbacks for data updates
  onPriceUpdate: (symbol, price) => {
    console.log(`${symbol}: $${price}`);
    // Update your chart or state here
  },
  onCandleUpdate: (symbol, candle) => {
    console.log(`${symbol} candle:`, candle);
    // Update your candlestick chart here
  },
});

// Connect to WebSocket
marketData.connect();

// Subscribe to symbols
marketData.subscribe('BTC/USDT', 'crypto');
marketData.subscribe('AAPL', 'stock');
marketData.subscribe('EUR/USD', 'forex');

// Cleanup on unmount
marketData.disconnect();
*/

export default MarketDataService;
