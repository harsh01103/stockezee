// test change
import { useState, useEffect, useRef } from 'react';
import { 
  TrendingUp, TrendingDown, Clock, Wallet, ChevronDown, 
  Settings, Plus, Minus, BarChart3, LineChart as LineChartIcon, 
  CandlestickChart, History, Bell
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { createChart, CandlestickSeries, LineSeries, type IChartApi, type ISeriesApi, type CandlestickData, type Time } from 'lightweight-charts';

interface Trade {
  id: string;
  type: 'up' | 'down';
  symbol: string;
  entryPrice: number;
  amount: number;
  timestamp: Date;
  expiryTime: Date;
  result?: 'win' | 'loss' | 'pending';
  payout?: number;
}

interface Asset {
  symbol: string;
  name: string;
  price: number;
  change: number;
  payout: number;
  category: 'crypto' | 'forex' | 'stocks' | 'commodities';
}

// Generate realistic candlestick data
const generateInitialData = (basePrice: number, count: number = 100): CandlestickData[] => {
  const data: CandlestickData[] = [];
  let price = basePrice;
  let time = new Date();
  time.setMinutes(time.getMinutes() - count);

  for (let i = 0; i < count; i++) {
    const volatility = price * 0.002;
    const change = (Math.random() - 0.5) * volatility;
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) + Math.random() * volatility * 0.5;
    const low = Math.min(open, close) - Math.random() * volatility * 0.5;

    data.push({
      time: time.getTime() / 1000 as Time,
      open: parseFloat(open.toFixed(4)),
      high: parseFloat(high.toFixed(4)),
      low: parseFloat(low.toFixed(4)),
      close: parseFloat(close.toFixed(4)),
    });

    price = close;
    time.setMinutes(time.getMinutes() + 1);
  }

  return data;
};

const assets: Asset[] = [
  { symbol: 'BTC/USD', name: 'Bitcoin', price: 43250.50, change: 2.35, payout: 87, category: 'crypto' },
  { symbol: 'ETH/USD', name: 'Ethereum', price: 2580.75, change: 1.82, payout: 85, category: 'crypto' },
  { symbol: 'EUR/USD', name: 'Euro/Dollar', price: 1.0845, change: 0.25, payout: 82, category: 'forex' },
  { symbol: 'GBP/USD', name: 'Pound/Dollar', price: 1.2630, change: -0.15, payout: 80, category: 'forex' },
  { symbol: 'USD/JPY', name: 'Dollar/Yen', price: 149.85, change: 0.42, payout: 81, category: 'forex' },
  { symbol: 'AAPL', name: 'Apple Inc.', price: 185.92, change: 1.15, payout: 78, category: 'stocks' },
  { symbol: 'GOOGL', name: 'Alphabet', price: 142.30, change: -0.85, payout: 76, category: 'stocks' },
  { symbol: 'TSLA', name: 'Tesla', price: 238.45, change: 3.25, payout: 79, category: 'stocks' },
  { symbol: 'GOLD', name: 'Gold', price: 2035.60, change: 0.65, payout: 83, category: 'commodities' },
  { symbol: 'OIL', name: 'Crude Oil', price: 76.85, change: -1.20, payout: 80, category: 'commodities' },
];

const timeframes = [
  { label: '15s', seconds: 15 },
  { label: '1m', seconds: 60 },
  { label: '5m', seconds: 300 },
  { label: '15m', seconds: 900 },
  { label: '1h', seconds: 3600 },
];

export function DemoPage() {
  // Account state
  const [balance, setBalance] = useState(10000);
  const [demoMode, setDemoMode] = useState(true);
  
  // Trading state
  const [selectedAsset, setSelectedAsset] = useState<Asset>(assets[0]);
  const [selectedTimeframe, setSelectedTimeframe] = useState(timeframes[1]);
  const [tradeAmount, setTradeAmount] = useState(100);
  const [activeTrades, setActiveTrades] = useState<Trade[]>([]);
  const [tradeHistory, setTradeHistory] = useState<Trade[]>([]);
  const [currentPrice, setCurrentPrice] = useState(assets[0].price);
  
  // UI state
  const [showAssetPanel, setShowAssetPanel] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [chartType, setChartType] = useState<'candles' | 'line' | 'bars'>('candles');
  
  // Chart refs
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const lineSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const lastPriceRef = useRef<number>(assets[0].price);

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: '#050505' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#111111' },
        horzLines: { color: '#111111' },
      },
      crosshair: {
        mode: 1,
        vertLine: {
          color: '#22c55e',
          labelBackgroundColor: '#22c55e',
        },
        horzLine: {
          color: '#22c55e',
          labelBackgroundColor: '#22c55e',
        },
      },
      rightPriceScale: {
        borderColor: '#333333',
      },
      timeScale: {
        borderColor: '#333333',
        timeVisible: true,
        secondsVisible: true,
        tickMarkFormatter: (time: number, tickMarkType: any) => {
          const dt = new Date(time * 1000);
          if (tickMarkType === 0) {
            return dt.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', year: 'numeric' });
          } else if (tickMarkType === 1 || tickMarkType === 2) {
            return dt.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', month: 'short', day: 'numeric' });
          } else {
            return dt.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true });
          }
        }
      },
      localization: {
        timeFormatter: (time: number) => {
          return new Intl.DateTimeFormat('en-IN', {
            timeZone: 'Asia/Kolkata',
            hour: 'numeric',
            minute: 'numeric',
            year: 'numeric',
            month: 'short',
            day: 'numeric'
          }).format(new Date(time * 1000));
        }
      },
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight,
    });

    chartRef.current = chart;

    // Add candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries);
    candleSeries.applyOptions({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });

    seriesRef.current = candleSeries;

    // Add line series (hidden by default)
    const lineSeries = chart.addSeries(LineSeries);
    lineSeries.applyOptions({
      color: '#22c55e',
      lineWidth: 2,
      visible: false,
    });

    lineSeriesRef.current = lineSeries;

    // Load initial data
    const initialData = generateInitialData(selectedAsset.price);
    candleSeries.setData(initialData);
    
    // Set line data
    const lineData = initialData.map(d => ({
      time: d.time,
      value: d.close,
    }));
    lineSeries.setData(lineData);

    // Fit content
    chart.timeScale().fitContent();

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  // Update chart when asset changes
  useEffect(() => {
    if (seriesRef.current && lineSeriesRef.current) {
      const newData = generateInitialData(selectedAsset.price);
      seriesRef.current.setData(newData);
      
      const lineData = newData.map(d => ({
        time: d.time,
        value: d.close,
      }));
      lineSeriesRef.current.setData(lineData);
      
      chartRef.current?.timeScale().fitContent();
      setCurrentPrice(selectedAsset.price);
    }
  }, [selectedAsset]);

  // Real-time price update simulation
  useEffect(() => {
    const interval = setInterval(() => {
      const volatility = selectedAsset.price * 0.0005;
      const change = (Math.random() - 0.5) * volatility;
      const newPrice = parseFloat((currentPrice + change).toFixed(selectedAsset.price > 100 ? 2 : 4));
      setCurrentPrice(newPrice);

      // Update chart with new candle
      if (seriesRef.current && lineSeriesRef.current) {
        const data = seriesRef.current.data();
        const lastCandle = data[data.length - 1] as CandlestickData | undefined;
        if (lastCandle && 'open' in lastCandle) {
          const updatedCandle: CandlestickData = {
            time: lastCandle.time,
            open: lastCandle.open,
            high: Math.max(lastCandle.high, newPrice),
            low: Math.min(lastCandle.low, newPrice),
            close: newPrice,
          };
          seriesRef.current.update(updatedCandle);
          lineSeriesRef.current.update({ time: lastCandle.time, value: newPrice });
        }
      }

      // Check active trades for expiry
      setActiveTrades(prev => {
        const now = new Date();
        const expired = prev.filter(t => t.expiryTime <= now);
        const stillActive = prev.filter(t => t.expiryTime > now);
        
        if (expired.length > 0) {
          expired.forEach(trade => {
            const won = trade.type === 'up' 
              ? newPrice > trade.entryPrice 
              : newPrice < trade.entryPrice;
            
            const payout = won 
              ? trade.amount * (1 + selectedAsset.payout / 100) 
              : 0;
            
            setBalance(b => b + payout);
            setTradeHistory(h => [{
              ...trade,
              result: won ? 'win' : 'loss',
              payout,
            }, ...h]);
          });
        }
        
        return stillActive;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [currentPrice, selectedAsset]);

  // Add new candle every minute
  useEffect(() => {
    lastPriceRef.current = currentPrice;
  }, [currentPrice]);

  useEffect(() => {
    const interval = setInterval(() => {
      if (seriesRef.current && lineSeriesRef.current) {
        const now = Math.floor(Date.now() / 1000) as Time;
        const price = lastPriceRef.current;
        const newCandle: CandlestickData = {
          time: now,
          open: price,
          high: price,
          low: price,
          close: price,
        };
        seriesRef.current.update(newCandle);
        lineSeriesRef.current.update({ time: now, value: price });
      }
    }, 60000);

    return () => clearInterval(interval);
  }, []);

  const handleTrade = (type: 'up' | 'down') => {
    if (tradeAmount > balance) return;

    const newTrade: Trade = {
      id: Date.now().toString(),
      type,
      symbol: selectedAsset.symbol,
      entryPrice: currentPrice,
      amount: tradeAmount,
      timestamp: new Date(),
      expiryTime: new Date(Date.now() + selectedTimeframe.seconds * 1000),
      result: 'pending',
    };

    setBalance(prev => prev - tradeAmount);
    setActiveTrades(prev => [newTrade, ...prev]);
  };

  const filteredAssets = selectedCategory === 'all' 
    ? assets 
    : assets.filter(a => a.category === selectedCategory);

  const switchChartType = (type: 'candles' | 'line' | 'bars') => {
    setChartType(type);
    if (seriesRef.current && lineSeriesRef.current) {
      seriesRef.current.applyOptions({ visible: type === 'candles' || type === 'bars' });
      lineSeriesRef.current.applyOptions({ visible: type === 'line' });
    }
  };

  return (
    <div className="h-[calc(100vh-72px)] bg-[#050505] flex flex-col animate-in fade-in duration-500">
      {/* Top Navigation Bar */}
      <div className="h-14 bg-[#0a0a0a] border-b border-[#333333] flex items-center justify-between px-4">
        {/* Left: Balance & Account */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-[#22c55e]/20 rounded-lg flex items-center justify-center">
              <Wallet className="w-4 h-4 text-[#22c55e]" />
            </div>
            <div>
              <p className="text-xs text-[#64748b]">Balance</p>
              <p className="font-bold text-[#22c55e]">${balance.toLocaleString()}</p>
            </div>
          </div>
          
          <Badge 
            variant="outline" 
            className={`cursor-pointer ${demoMode ? 'border-[#22c55e] text-[#22c55e]' : 'border-[#f59e0b] text-[#f59e0b]'}`}
            onClick={() => setDemoMode(!demoMode)}
          >
            {demoMode ? 'Demo Account' : 'Real Account'}
          </Badge>
        </div>

        {/* Center: Asset Selector */}
        <button 
          onClick={() => setShowAssetPanel(!showAssetPanel)}
          className="flex items-center gap-3 px-4 py-2 bg-[#111111] rounded-lg border border-[#333333] hover:border-[#4a5568] transition-colors"
        >
          <div className="w-8 h-8 bg-gradient-to-br from-[#22c55e] to-[#16a34a] rounded-lg flex items-center justify-center text-white font-bold text-xs">
            {selectedAsset.symbol.split('/')[0].slice(0, 2)}
          </div>
          <div className="text-left">
            <p className="font-semibold text-sm">{selectedAsset.symbol}</p>
            <p className="text-xs text-[#64748b]">{selectedAsset.name}</p>
          </div>
          <div className="text-right ml-4">
            <p className="font-mono text-sm">{currentPrice.toFixed(selectedAsset.price > 100 ? 2 : 4)}</p>
            <p className={`text-xs ${selectedAsset.change >= 0 ? 'text-[#22c55e]' : 'text-[#ef4444]'}`}>
              {selectedAsset.change >= 0 ? '+' : ''}{selectedAsset.change}%
            </p>
          </div>
          <ChevronDown className="w-4 h-4 text-[#64748b]" />
        </button>

        {/* Right: Timer & Settings */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-[#94a3b8]">
            <Clock className="w-4 h-4" />
            <span className="text-sm font-mono">{new Date().toLocaleTimeString()}</span>
          </div>
          <button className="p-2 hover:bg-white/5 rounded-lg transition-colors">
            <Bell className="w-5 h-5 text-[#94a3b8]" />
          </button>
          <button className="p-2 hover:bg-white/5 rounded-lg transition-colors">
            <Settings className="w-5 h-5 text-[#94a3b8]" />
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Asset Panel (Collapsible) */}
        {showAssetPanel && (
          <div className="w-72 bg-[#0a0a0a] border-r border-[#333333] flex flex-col">
            {/* Category Tabs */}
            <div className="flex border-b border-[#333333]">
              {['all', 'crypto', 'forex', 'stocks', 'commodities'].map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`flex-1 py-3 text-xs font-medium capitalize transition-colors ${
                    selectedCategory === cat 
                      ? 'text-[#22c55e] border-b-2 border-[#22c55e]' 
                      : 'text-[#64748b] hover:text-white'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            {/* Asset List */}
            <div className="flex-1 overflow-y-auto">
              {filteredAssets.map((asset) => (
                <button
                  key={asset.symbol}
                  onClick={() => {
                    setSelectedAsset(asset);
                    setShowAssetPanel(false);
                  }}
                  className={`w-full p-4 flex items-center justify-between border-b border-[#333333] hover:bg-white/5 transition-colors ${
                    selectedAsset.symbol === asset.symbol ? 'bg-[#22c55e]/10' : ''
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-[#22c55e] to-[#16a34a] rounded-lg flex items-center justify-center text-white font-bold text-xs">
                      {asset.symbol.split('/')[0].slice(0, 2)}
                    </div>
                    <div className="text-left">
                      <p className="font-semibold text-sm">{asset.symbol}</p>
                      <p className="text-xs text-[#64748b]">{asset.name}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-mono text-sm">{asset.price.toFixed(asset.price > 100 ? 2 : 4)}</p>
                    <p className={`text-xs ${asset.change >= 0 ? 'text-[#22c55e]' : 'text-[#ef4444]'}`}>
                      {asset.change >= 0 ? '+' : ''}{asset.change}%
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Chart Area */}
        <div className="flex-1 flex flex-col">
          {/* Chart Toolbar */}
          <div className="h-10 bg-[#050505] border-b border-[#333333] flex items-center justify-between px-4">
            <div className="flex items-center gap-2">
              {/* Chart Type Buttons */}
              <div className="flex bg-[#111111] rounded-lg p-1">
                <button
                  onClick={() => switchChartType('candles')}
                  className={`p-1.5 rounded transition-colors ${chartType === 'candles' ? 'bg-[#22c55e] text-white' : 'text-[#94a3b8] hover:text-white'}`}
                  title="Candlestick"
                >
                  <CandlestickChart className="w-4 h-4" />
                </button>
                <button
                  onClick={() => switchChartType('line')}
                  className={`p-1.5 rounded transition-colors ${chartType === 'line' ? 'bg-[#22c55e] text-white' : 'text-[#94a3b8] hover:text-white'}`}
                  title="Line"
                >
                  <LineChartIcon className="w-4 h-4" />
                </button>
                <button
                  onClick={() => switchChartType('bars')}
                  className={`p-1.5 rounded transition-colors ${chartType === 'bars' ? 'bg-[#22c55e] text-white' : 'text-[#94a3b8] hover:text-white'}`}
                  title="Bars"
                >
                  <BarChart3 className="w-4 h-4" />
                </button>
              </div>

              <div className="w-px h-6 bg-[#333333] mx-2" />

              {/* Timeframe Selector */}
              <div className="flex gap-1">
                {timeframes.map((tf) => (
                  <button
                    key={tf.label}
                    onClick={() => setSelectedTimeframe(tf)}
                    className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                      selectedTimeframe.label === tf.label
                        ? 'bg-[#22c55e] text-white'
                        : 'text-[#94a3b8] hover:text-white hover:bg-white/5'
                    }`}
                  >
                    {tf.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Indicators Button */}
            <button className="flex items-center gap-2 px-3 py-1.5 text-sm text-[#94a3b8] hover:text-white hover:bg-white/5 rounded-lg transition-colors">
              <TrendingUp className="w-4 h-4" />
              Indicators
            </button>
          </div>

          {/* Chart Container */}
          <div 
            ref={chartContainerRef}
            className="flex-1 relative"
          />

          {/* Current Price Indicator */}
          <div className="absolute top-24 right-8 bg-[#111111] border border-[#333333] rounded-lg px-4 py-2">
            <p className="text-xs text-[#64748b]">Current Price</p>
            <p className="text-xl font-mono font-bold text-white">{currentPrice.toFixed(selectedAsset.price > 100 ? 2 : 4)}</p>
          </div>
        </div>

        {/* Right Panel - Trade History */}
        <div className="w-80 bg-[#0a0a0a] border-l border-[#333333] flex flex-col">
          <div className="p-4 border-b border-[#333333]">
            <h3 className="font-semibold flex items-center gap-2">
              <History className="w-4 h-4" />
              Trade History
            </h3>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {/* Active Trades */}
            {activeTrades.length > 0 && (
              <div>
                <p className="text-xs text-[#64748b] uppercase tracking-wider mb-2">Active Trades</p>
                {activeTrades.map((trade) => (
                  <div key={trade.id} className="bg-[#111111] border border-[#333333] rounded-lg p-3 mb-2">
                    <div className="flex items-center justify-between mb-2">
                      <Badge className={trade.type === 'up' ? 'bg-[#22c55e]' : 'bg-[#ef4444]'}>
                        {trade.type === 'up' ? 'UP' : 'DOWN'}
                      </Badge>
                      <span className="text-xs text-[#64748b]">{trade.symbol}</span>
                    </div>
                    <div className="space-y-1 text-sm">
                      <div className="flex justify-between">
                        <span className="text-[#64748b]">Amount:</span>
                        <span>${trade.amount}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[#64748b]">Entry:</span>
                        <span className="font-mono">{trade.entryPrice.toFixed(4)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[#64748b]">Expires:</span>
                        <span className="text-[#f59e0b]">
                          {Math.ceil((trade.expiryTime.getTime() - Date.now()) / 1000)}s
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Completed Trades */}
            {tradeHistory.length > 0 && (
              <div>
                <p className="text-xs text-[#64748b] uppercase tracking-wider mb-2">Completed</p>
                {tradeHistory.slice(0, 10).map((trade) => (
                  <div key={trade.id} className="bg-[#111111] border border-[#333333] rounded-lg p-3 mb-2">
                    <div className="flex items-center justify-between mb-2">
                      <Badge className={trade.type === 'up' ? 'bg-[#22c55e]' : 'bg-[#ef4444]'}>
                        {trade.type === 'up' ? 'UP' : 'DOWN'}
                      </Badge>
                      <Badge className={trade.result === 'win' ? 'bg-[#22c55e]' : 'bg-[#ef4444]'}>
                        {trade.result === 'win' ? `+$${trade.payout?.toFixed(2)}` : 'LOSS'}
                      </Badge>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-[#64748b]">{trade.symbol}</span>
                      <span className="text-[#64748b]">{trade.timestamp.toLocaleTimeString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {activeTrades.length === 0 && tradeHistory.length === 0 && (
              <div className="text-center py-8 text-[#64748b]">
                <History className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>No trades yet</p>
                <p className="text-sm mt-1">Start trading to see history</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Trading Panel */}
      <div className="h-24 bg-[#0a0a0a] border-t border-[#333333] px-6 flex items-center justify-between">
        {/* Amount Controls */}
        <div className="flex items-center gap-4">
          <div>
            <p className="text-xs text-[#64748b] mb-1">Investment Amount</p>
            <div className="flex items-center gap-2">
              <button 
                onClick={() => setTradeAmount(Math.max(10, tradeAmount - 10))}
                className="w-10 h-10 bg-[#111111] border border-[#333333] rounded-lg flex items-center justify-center hover:border-[#4a5568] transition-colors"
              >
                <Minus className="w-4 h-4" />
              </button>
              <div className="w-28 h-10 bg-[#111111] border border-[#333333] rounded-lg flex items-center justify-center">
                <span className="font-mono font-bold">${tradeAmount}</span>
              </div>
              <button 
                onClick={() => setTradeAmount(Math.min(balance, tradeAmount + 10))}
                className="w-10 h-10 bg-[#111111] border border-[#333333] rounded-lg flex items-center justify-center hover:border-[#4a5568] transition-colors"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="w-px h-12 bg-[#333333]" />

          <div>
            <p className="text-xs text-[#64748b] mb-1">Potential Profit</p>
            <p className="text-lg font-bold text-[#22c55e]">
              +${(tradeAmount * selectedAsset.payout / 100).toFixed(2)}
            </p>
            <p className="text-xs text-[#64748b]">{selectedAsset.payout}% payout</p>
          </div>
        </div>

        {/* Trade Buttons */}
        <div className="flex items-center gap-4">
          {/* Down Button */}
          <button
            onClick={() => handleTrade('down')}
            disabled={tradeAmount > balance}
            className="w-40 h-16 bg-gradient-to-b from-[#ef4444] to-[#dc2626] rounded-xl flex flex-col items-center justify-center shadow-lg shadow-red-500/20 hover:shadow-red-500/40 transition-all disabled:opacity-50 disabled:cursor-not-allowed active:scale-95"
          >
            <TrendingDown className="w-6 h-6 mb-1" />
            <span className="font-bold text-lg">DOWN</span>
          </button>

          {/* Up Button */}
          <button
            onClick={() => handleTrade('up')}
            disabled={tradeAmount > balance}
            className="w-40 h-16 bg-gradient-to-b from-[#22c55e] to-[#16a34a] rounded-xl flex flex-col items-center justify-center shadow-lg shadow-green-500/20 hover:shadow-green-500/40 transition-all disabled:opacity-50 disabled:cursor-not-allowed active:scale-95"
          >
            <TrendingUp className="w-6 h-6 mb-1" />
            <span className="font-bold text-lg">UP</span>
          </button>
        </div>
      </div>
    </div>
  );
}
