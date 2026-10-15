import React, { useState, useEffect } from 'react';
import axios from 'axios';
import type { Instrument } from '../components/StockSearch';
import StockChart from '../components/StockChart';
import TradeHistory from '../components/TradeHistory';
import { Search, SlidersHorizontal, ArrowRightLeft, Briefcase, X, BarChart2, LineChart, TrendingUp } from 'lucide-react';
import { useDemoStore } from '../store/demoStore';
import { addTrade } from '../store/tradeLog';

const COMMODITIES: Instrument[] = [
    { instrument_key: "COMM|GOLD", symbol: "GOLD", name: "Gold (10g)", exchange: "MCX" },
    { instrument_key: "COMM|SILVER", symbol: "SILVER", name: "Silver (1kg)", exchange: "MCX" },
    { instrument_key: "COMM|CRUDEOIL", symbol: "CRUDEOIL", name: "Crude Oil", exchange: "MCX" },
    { instrument_key: "COMM|NATURALGAS", symbol: "NATURALGAS", name: "Natural Gas", exchange: "MCX" },
];

const MarketStatusBadge = ({ type }: { type: 'stock' | 'commodity' }) => {
    const [statusData, setStatusData] = useState({ status: '...', color: 'text-slate-500' });

    useEffect(() => {
        const updateStatus = () => {
            const now = new Date();
            const istTime = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
            const day = istTime.getDay();
            const hours = istTime.getHours();
            const minutes = istTime.getMinutes();
            const timeInMinutes = hours * 60 + minutes;

            if (day === 0 || day === 6) {
                setStatusData({ status: "Market Closed (Weekend)", color: "bg-red-500/10 text-red-500 border border-red-500/20" });
                return;
            }

            if (type === 'stock') {
                const preMarketStart = 9 * 60;
                const preMarketEnd = 9 * 60 + 15;
                const marketEnd = 15 * 60 + 30;
                const postMarketEnd = 16 * 60;

                if (timeInMinutes >= preMarketStart && timeInMinutes < preMarketEnd) setStatusData({ status: "Pre-Market", color: "bg-yellow-500/10 text-yellow-500 border border-yellow-500/20" });
                else if (timeInMinutes >= preMarketEnd && timeInMinutes < marketEnd) setStatusData({ status: "Market Live", color: "bg-[#22c55e]/10 text-[#22c55e] border border-[#22c55e]/20" });
                else if (timeInMinutes >= marketEnd && timeInMinutes < postMarketEnd) setStatusData({ status: "Post-Market", color: "bg-orange-500/10 text-orange-500 border border-orange-500/20" });
                else setStatusData({ status: "Market Closed", color: "bg-red-500/10 text-red-500 border border-red-500/20" });
            } else {
                const morningStart = 9 * 60;
                const eveningStart = 17 * 60;
                const eveningEnd = 23 * 60 + 30;

                if (timeInMinutes >= morningStart && timeInMinutes < eveningStart) setStatusData({ status: "Morning Session Live", color: "bg-[#22c55e]/10 text-[#22c55e] border border-[#22c55e]/20" });
                else if (timeInMinutes >= eveningStart && timeInMinutes < eveningEnd) setStatusData({ status: "Evening Session Live", color: "bg-[#22c55e]/10 text-[#22c55e] border border-[#22c55e]/20" });
                else setStatusData({ status: "Market Closed", color: "bg-red-500/10 text-red-500 border border-red-500/20" });
            }
        };
        updateStatus();
        const interval = setInterval(updateStatus, 60000);
        return () => clearInterval(interval);
    }, [type]);

    return (
        <span className={`px-2.5 py-1 rounded-full flex items-center gap-1.5 shadow-sm ${statusData.color}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${statusData.color.includes('red') ? 'bg-red-500' : statusData.color.includes('yellow') ? 'bg-yellow-500' : statusData.color.includes('orange') ? 'bg-orange-500' : 'bg-[#22c55e] animate-pulse'}`}></span>
            <span className="text-[10px] font-bold uppercase tracking-widest">{statusData.status}</span>
        </span>
    );
};

const DemoCommoditiesTrading: React.FC = () => {
    const [selectedStock, setSelectedStock] = useState<Instrument | null>(COMMODITIES[0]);
    const [ltp, setLtp] = useState<number | null>(null);
    const [prevLtp, setPrevLtp] = useState<number | null>(null);
    const [chartData, setChartData] = useState<any[]>([]);
    const [loadingChart, setLoadingChart] = useState(false);
    const [interval, setIntervalState] = useState('1m');
    const [chartType, setChartType] = useState<'candle' | 'line'>('candle');

    // Indicators
    const defaultIndicators = {
        sma: { enabled: false, period: 20, color: '#3b82f6' },
        ema: { enabled: false, period: 50, color: '#f59e0b' },
        vwap: { enabled: false, color: '#eab308' },
        bb: { enabled: false, period: 20, stdDev: 2, color: '#06b6d4' },
        rsi: { enabled: false, period: 14, color: '#a855f7' },
        macd: { enabled: false, fast: 12, slow: 26, signal: 9, color: '#fb7185' },
        stoch: { enabled: false, period: 14, signal: 3, color: '#10b981' },
        atr: { enabled: false, period: 14, color: '#8b5cf6' },
        adx: { enabled: false, period: 14, color: '#f97316' },
        obv: { enabled: false, color: '#3b82f6' },
        volume: { enabled: false, color: '#64748b' },
        ichimoku: { enabled: false, conversion: 9, base: 26, span: 52, displacement: 26, color: '#14b8a6' },
        cci: { enabled: false, period: 20, color: '#ec4899' },
        williamsr: { enabled: false, period: 14, color: '#0ea5e9' },
        mfi: { enabled: false, period: 14, color: '#14b8a6' },
        kc: { enabled: false, period: 20, multiplier: 1, color: '#8b5cf6' },
    };
    const [indicatorConfig, setIndicatorConfig] = useState<any>(defaultIndicators);
    const [showIndicatorMenu, setShowIndicatorMenu] = useState(false);
    const [indicatorSearch, setIndicatorSearch] = useState('');
    const [settingsModal, setSettingsModal] = useState<string | null>(null);
    const [tempSettings, setTempSettings] = useState<any>(null);

    const updateIndicatorSettings = (key: string, field: string, value: any) => {
        if (field === 'all') {
            setIndicatorConfig((prev: any) => ({ ...prev, [key]: { ...prev[key], ...value } }));
        } else {
            setIndicatorConfig((prev: any) => ({ ...prev, [key]: { ...prev[key], [field]: value } }));
        }
    };

    const allIndicatorsList = [
        {
            category: 'Trend Following', items: [
                { key: 'sma', label: 'Simple Moving Average (SMA)', fields: [{ name: 'period', type: 'number', label: 'Period' }] },
                { key: 'ema', label: 'Exponential Moving Average (EMA)', fields: [{ name: 'period', type: 'number', label: 'Period' }] },
                { key: 'rsi', label: 'Relative Strength Index (RSI)', fields: [{ name: 'period', type: 'number', label: 'Period' }] },
                { key: 'macd', label: 'Moving Average Convergence Divergence (MACD)', fields: [{ name: 'fast', type: 'number', label: 'Fast' }, { name: 'slow', type: 'number', label: 'Slow' }, { name: 'signal', type: 'number', label: 'Signal' }] },
                { key: 'adx', label: 'Average Directional Index (ADX)', fields: [{ name: 'period', type: 'number', label: 'Period' }] }
            ]
        },
        {
            category: 'Oscillators', items: [
                { key: 'stoch', label: 'Stochastic Oscillator', fields: [{ name: 'period', type: 'number', label: 'Period' }, { name: 'signal', type: 'number', label: 'Signal' }] },
                { key: 'cci', label: 'Commodity Channel Index (CCI)', fields: [{ name: 'period', type: 'number', label: 'Period' }] },
                { key: 'williamsr', label: 'Williams %R', fields: [{ name: 'period', type: 'number', label: 'Period' }] },
                { key: 'mfi', label: 'Money Flow Index (MFI)', fields: [{ name: 'period', type: 'number', label: 'Period' }] }
            ]
        },
        {
            category: 'Volatility', items: [
                { key: 'atr', label: 'Average True Range (ATR)', fields: [{ name: 'period', type: 'number', label: 'Period' }] },
                { key: 'bb', label: 'Bollinger Bands', fields: [{ name: 'period', type: 'number', label: 'Period' }, { name: 'stdDev', type: 'number', label: 'Std Dev' }] },
                { key: 'kc', label: 'Keltner Channels', fields: [{ name: 'period', type: 'number', label: 'Period' }, { name: 'multiplier', type: 'number', label: 'Multiplier' }] }
            ]
        },
        {
            category: 'Volume', items: [
                { key: 'obv', label: 'On-Balance Volume (OBV)', fields: [] },
                { key: 'vwap', label: 'Volume-Weighted Average Price (VWAP)', fields: [] },
                { key: 'volume', label: 'Volume', fields: [] }
            ]
        },
        {
            category: 'Support & Resistance', items: [
                { key: 'ichimoku', label: 'Ichimoku Cloud', fields: [{ name: 'conversion', type: 'number', label: 'Conv' }, { name: 'base', type: 'number', label: 'Base' }, { name: 'span', type: 'number', label: 'Span' }, { name: 'displacement', type: 'number', label: 'Disp' }] }
            ]
        }
    ];

    // Trading state
    const [qty, setQty] = useState<number>(1);
    const { cash, setCash, positions, setPositions } = useDemoStore();

    const fetchStockData = async (instrument: Instrument, timeframe: string) => {
        try {
            setLoadingChart(true);
            const [ltpRes, intradayRes] = await Promise.all([
                axios.get(`/api/ltp?instrument_key=${instrument.instrument_key}`),
                axios.get(`/api/intraday?instrument_key=${instrument.instrument_key}&interval=${timeframe}`)
            ]);
            setPrevLtp(ltp);
            setLtp(ltpRes.data.last_price);
            setChartData(intradayRes.data);
        } catch (err) {
            console.error("Error fetching data", err);
        } finally {
            setLoadingChart(false);
        }
    };

    useEffect(() => {
        if (!selectedStock) return;
        fetchStockData(selectedStock, interval);
        const intervalId = setInterval(() => {
            const now = new Date();
            const istTime = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
            const day = istTime.getDay();
            const timeInMins = istTime.getHours() * 60 + istTime.getMinutes();
            // Commodities Open Mon-Fri 9:00 AM (540m) to 11:30 PM (1410m)
            const isOpen = day >= 1 && day <= 5 && timeInMins >= 540 && timeInMins <= 1410;

            if (!isOpen) return;

            axios.get(`/api/ltp?instrument_key=${selectedStock.instrument_key}`)
                .then(res => {
                    const price = res.data.last_price;
                    setPrevLtp(prev => prev !== price ? price : prev);
                    setLtp(price);
                    setChartData(prev => {
                        if (!prev || prev.length === 0) return prev;
                        const newData = [...prev];
                        const lastIdx = newData.length - 1;
                        const updatedCandle = { ...newData[lastIdx] };
                        updatedCandle.close = price;
                        if (price > updatedCandle.high) updatedCandle.high = price;
                        if (price < updatedCandle.low) updatedCandle.low = price;
                        newData[lastIdx] = updatedCandle;
                        return newData;
                    });
                })
                .catch(() => { });
        }, 2000); // Poll LTP every 2s when market open
        return () => clearInterval(intervalId);
    }, [selectedStock, interval]);

    const checkMarketOpen = () => {
        const now = new Date();
        const istTime = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
        const day = istTime.getDay();
        const hours = istTime.getHours();
        const mins = istTime.getMinutes();
        const timeInMins = hours * 60 + mins;
        // Mon-Fri (1-5), 9:00 AM (540) to 11:30 PM (1410)
        return day >= 1 && day <= 5 && timeInMins >= 540 && timeInMins <= 1410;
    };

    const handleSelectStock = (stock: Instrument) => {
        let defaultExch = stock.exchange;
        let defaultKey = stock.instrument_key;
        if (stock.exchanges && stock.instrument_keys) {
            if (stock.exchanges.includes('NSE_EQ')) {
                defaultExch = 'NSE_EQ';
                defaultKey = stock.instrument_keys['NSE_EQ'];
            } else if (stock.exchanges.includes('BSE_EQ')) {
                defaultExch = 'BSE_EQ';
                defaultKey = stock.instrument_keys['BSE_EQ'];
            }
        }
        setSelectedStock({
            ...stock,
            exchange: defaultExch,
            instrument_key: defaultKey
        });
    };

    const handleExchangeToggle = (exch: string) => {
        if (selectedStock && selectedStock.instrument_keys && selectedStock.exchange !== exch) {
            setSelectedStock({
                ...selectedStock,
                exchange: exch,
                instrument_key: selectedStock.instrument_keys[exch]
            });
        }
    };

    const handleTrade = (type: 'BUY' | 'SELL') => {
        if (!selectedStock || !ltp || qty <= 0) return;

        if (!checkMarketOpen()) {
            alert("Market is closed. Please trade during Indian market hours (9:15 AM - 3:30 PM IST).");
            return;
        }

        const cost = ltp * qty;
        const currentPos = positions[selectedStock.symbol] || { symbol: selectedStock.symbol, qty: 0, avgPrice: 0 };

        if (type === 'BUY') {
            if (cash < cost) {
                alert("Not enough Demo Cash!");
                return;
            }
            const newQty = currentPos.qty + qty;
            const newAvgPrice = ((currentPos.qty * currentPos.avgPrice) + cost) / newQty;

            setPositions({ ...positions, [selectedStock.symbol]: { symbol: selectedStock.symbol, qty: newQty, avgPrice: newAvgPrice } });
            setCash(cash - cost);

            addTrade({
                symbol: selectedStock.symbol,
                name: selectedStock.name || selectedStock.symbol,
                type: 'BUY',
                qty,
                price: ltp,
                total: cost,
                category: 'commodity',
            });
        } else {
            // SELL
            if (currentPos.qty < qty) {
                alert("You don't have enough units to sell!");
                return;
            }
            const realizedPnl = (ltp - currentPos.avgPrice) * qty;
            const newQty = currentPos.qty - qty;
            const newPositions = { ...positions };
            if (newQty === 0) {
                delete newPositions[selectedStock.symbol];
            } else {
                newPositions[selectedStock.symbol] = { ...currentPos, qty: newQty };
            }
            setPositions(newPositions);
            setCash(cash + cost);

            addTrade({
                symbol: selectedStock.symbol,
                name: selectedStock.name || selectedStock.symbol,
                type: 'SELL',
                qty,
                price: ltp,
                total: cost,
                pnl: realizedPnl,
                category: 'commodity',
            });
        }
    };

    const currentPosition = selectedStock ? positions[selectedStock.symbol] : null;

    return (
        <div className="min-h-screen bg-[#050505] text-white font-sans selection:bg-[#22c55e]/30">
            {/* Background elements */}
            <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
                <div className="absolute top-0 right-1/4 w-[50vw] h-[50vw] bg-white/[0.015] blur-[150px] rounded-full mix-blend-screen" />
                <div className="absolute bottom-0 left-1/4 w-[40vw] h-[40vw] bg-[#22c55e]/5 blur-[120px] rounded-full mix-blend-screen" />
                <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.1] mix-blend-overlay pointer-events-none" />
            </div>

            <div className="relative z-10 max-w-[1400px] mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-8">
                <header className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-4 sm:gap-6 mb-6 sm:mb-8 mt-2 sm:mt-4">
                    <div>
                        <h1 className="text-2xl sm:text-3xl md:text-5xl font-extrabold text-[#22c55e] drop-shadow-sm mb-1 sm:mb-2">
                            Commodities Pro
                        </h1>
                        <p className="text-white/40 font-medium tracking-wide text-sm sm:text-base">Advanced Commodities Trading</p>
                    </div>
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4 w-full xl:w-auto">

                        <div className="flex flex-wrap bg-white/[0.01] border border-white/5 rounded-2xl overflow-hidden shadow-lg p-1 sm:mr-4 gap-1">
                            {COMMODITIES.map(comm => {
                                const isActive = selectedStock?.instrument_key === comm.instrument_key;
                                return (
                                    <button
                                        key={comm.instrument_key}
                                        onClick={() => handleSelectStock(comm)}
                                        className={`px-3 sm:px-6 py-2 sm:py-2.5 text-xs sm:text-sm font-bold tracking-wide rounded-lg transition-all flex-1 sm:flex-none ${isActive
                                            ? 'bg-[#22c55e] text-white shadow-[0_0_15px_rgba(34,197,94,0.3)]'
                                            : 'text-white/40 hover:text-white hover:bg-white/5'
                                            }`}
                                    >
                                        {comm.symbol}
                                    </button>
                                );
                            })}
                        </div>

                        {selectedStock && (
                            <div className="bg-white/[0.01] border border-white/5 px-4 sm:px-6 py-2 rounded-2xl flex flex-col items-center sm:items-end shadow-lg h-[50px] justify-center sm:ml-2">
                                <span className="text-[10px] font-bold text-white/40 uppercase tracking-wider leading-tight">Available Cash</span>
                                <span className="text-base sm:text-lg font-mono font-black text-[#22c55e] leading-tight">₹{cash.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                            </div>
                        )}
                    </div>
                </header>

                {selectedStock ? (
                    <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 sm:gap-6">

                        {/* Main Chart Area */}
                        <div className="lg:col-span-3 space-y-6">

                            {/* Header Card */}
                            <div className="bg-white/[0.02] border border-white/5 p-4 sm:p-6 flex flex-col sm:flex-row justify-between items-start sm:items-center shadow-2xl rounded-2xl sm:rounded-3xl relative z-20 backdrop-blur-xl hover:border-white/10 transition-colors">
                                <div className="relative z-10 flex flex-col gap-1 w-full">
                                    <div className="flex flex-wrap items-center gap-2 sm:gap-3">
                                        <div className="flex bg-slate-800 rounded p-0.5">
                                            {selectedStock.exchanges ? selectedStock.exchanges.map(exch => (
                                                <button
                                                    key={exch}
                                                    onClick={() => handleExchangeToggle(exch)}
                                                    className={`text-[10px] font-black uppercase tracking-widest px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-lg transition-colors ${selectedStock.exchange === exch ? 'bg-white/10 text-white shadow-sm border border-white/20' : 'text-white/40 hover:text-white/80 hover:bg-white/5'}`}
                                                >
                                                    {exch.replace('_EQ', '')}
                                                </button>
                                            )) : (
                                                <span className="text-slate-400 text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded">
                                                    {selectedStock.exchange.replace('_EQ', '')}
                                                </span>
                                            )}
                                        </div>
                                        <span className="text-slate-500 text-xs sm:text-sm truncate max-w-[120px] sm:max-w-xs">{selectedStock.name}</span>
                                        <MarketStatusBadge type="commodity" />
                                    </div>
                                    <div className="flex items-end gap-3 sm:gap-4 mt-1 w-full justify-between sm:justify-start">
                                        <h2 className="text-2xl sm:text-3xl md:text-4xl font-black text-white">{selectedStock.symbol}</h2>
                                        <div className="text-right sm:text-left shrink-0">
                                            <div className={`text-2xl sm:text-3xl md:text-4xl font-mono font-bold tracking-tight transition-colors duration-300 ${!prevLtp || ltp === prevLtp ? 'text-white' : (ltp! > prevLtp! ? 'text-[#22c55e]' : 'text-red-500')}`}>
                                                ₹{(ltp || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Timeframes & Indicators */}
                                <div className="relative z-10 flex flex-col items-start sm:items-end gap-3 mt-4 sm:mt-0 w-full sm:max-w-[600px]">
                                    <div className="flex items-center gap-2 w-full sm:w-auto sm:self-end">
                                        <div className="flex bg-[#050505] border border-[#333333] rounded-xl overflow-hidden">
                                            <button
                                                onClick={() => setChartType('candle')}
                                                className={`flex items-center justify-center p-2 transition-colors ${chartType === 'candle' ? 'bg-[#22c55e] text-white shadow-md' : 'text-slate-400 hover:text-white hover:bg-slate-700/50'}`}
                                                title="Candlestick Chart"
                                            >
                                                <BarChart2 size={16} />
                                            </button>
                                            <button
                                                onClick={() => setChartType('line')}
                                                className={`flex items-center justify-center p-2 transition-colors ${chartType === 'line' ? 'bg-[#22c55e] text-white shadow-md' : 'text-slate-400 hover:text-white hover:bg-slate-700/50'}`}
                                                title="Line Chart"
                                            >
                                                <LineChart size={16} />
                                            </button>
                                        </div>
                                        <div className="flex gap-1 sm:gap-2 p-1 bg-[#050505] border border-[#333333] rounded-xl flex-1 sm:flex-none">
                                            {['1m', '5m', '15m', '1h', '1d'].map(tf => (
                                                <button
                                                    key={tf}
                                                    onClick={() => setIntervalState(tf)}
                                                    className={`px-2 sm:px-3 py-1 text-xs sm:text-sm font-bold rounded-lg transition-colors flex-1 sm:flex-none ${interval === tf ? 'bg-[#22c55e] text-white shadow-md' : 'text-slate-400 hover:text-white hover:bg-slate-700/50'}`}
                                                >
                                                    {tf}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="flex flex-wrap justify-end items-center gap-2 w-full relative">
                                        {Object.entries(indicatorConfig)
                                            .filter(([_, conf]: any) => conf.enabled)
                                            .map(([key, _]: any) => (
                                                <div key={key} className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-800/80 border border-slate-700/50 rounded-md text-xs font-bold text-slate-300 shadow-sm">
                                                    <span className="uppercase">{key}</span>
                                                    <button
                                                        onClick={() => updateIndicatorSettings(key, 'enabled', false)}
                                                        className="text-slate-500 hover:text-red-400 p-0.5 rounded-full hover:bg-slate-700 transition-all"
                                                        title={`Remove ${key.toUpperCase()}`}
                                                    >
                                                        <X size={12} strokeWidth={3} />
                                                    </button>
                                                </div>
                                            ))}
                                        <button
                                            onClick={() => setShowIndicatorMenu(true)}
                                            className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-white/[0.05] border border-white/10 text-white hover:text-white hover:bg-white/10 transition-colors shadow-lg"
                                        >
                                            <SlidersHorizontal size={14} className="text-[#22c55e]" />
                                            <span className="text-[10px] uppercase font-black tracking-widest">Indicators</span>
                                        </button>

                                        {showIndicatorMenu && (
                                            <>
                                                <div className="fixed inset-0 z-40" onClick={() => setShowIndicatorMenu(false)}></div>
                                                <div className="fixed inset-4 sm:absolute sm:inset-auto sm:top-12 sm:right-0 z-50 bg-[#0f1629] border border-slate-700 sm:w-80 max-h-[80vh] sm:max-h-[60vh] flex flex-col rounded-xl shadow-2xl overflow-hidden">
                                                    <div className="flex items-center p-3 border-b border-slate-800">
                                                        <h3 className="text-lg font-bold text-white">Indicators</h3>
                                                        <button onClick={() => setShowIndicatorMenu(false)} className="ml-auto text-slate-400 hover:text-white p-1"><X size={20} /></button>
                                                    </div>
                                                    <div className="p-2 border-b border-slate-800 flex items-center bg-slate-900 mx-3 mt-3 rounded">
                                                        <Search size={16} className="text-slate-400 mr-2" />
                                                        <input
                                                            type="text"
                                                            placeholder="Search"
                                                            value={indicatorSearch}
                                                            onChange={e => setIndicatorSearch(e.target.value)}
                                                            className="w-full bg-transparent text-sm text-white outline-none border-none py-1"
                                                        />
                                                    </div>
                                                    <div className="flex-1 overflow-y-auto p-2 space-y-4">
                                                        {allIndicatorsList.map(category => {
                                                            const filteredItems = category.items.filter(item => item.label.toLowerCase().includes(indicatorSearch.toLowerCase()));
                                                            if (filteredItems.length === 0) return null;
                                                            return (
                                                                <div key={category.category}>
                                                                    <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1 px-2">{category.category}</h4>
                                                                    <div className="space-y-0.5">
                                                                        {filteredItems.map(item => {
                                                                            const isEnabled = indicatorConfig[item.key]?.enabled;
                                                                            return (
                                                                                <div
                                                                                    key={item.key}
                                                                                    className={`flex justify-between items-center px-2 py-1.5 rounded transition-colors cursor-pointer hover:bg-slate-800`}
                                                                                    onClick={() => {
                                                                                        updateIndicatorSettings(item.key, 'enabled', !isEnabled);
                                                                                    }}
                                                                                >
                                                                                    <span className="text-slate-300 text-sm">{item.label}</span>
                                                                                    {isEnabled && (
                                                                                        <div className={`w-1.5 h-1.5 rounded-full bg-[#22c55e]`}></div>
                                                                                    )}
                                                                                </div>
                                                                            );
                                                                        })}
                                                                    </div>
                                                                </div>
                                                            );
                                                        })}
                                                    </div>
                                                </div>
                                            </>
                                        )}

                                        {settingsModal && tempSettings && (
                                            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 w-screen h-screen">
                                                <div className="bg-[#111111] border border-[#333333] w-full max-w-md rounded-xl shadow-2xl">
                                                    <div className="flex items-center justify-between p-4 border-b border-slate-800">
                                                        <h3 className="text-xl font-bold text-white uppercase tracking-wider">{settingsModal}</h3>
                                                        <button onClick={() => setSettingsModal(null)} className="text-slate-400 hover:text-white p-1"><X size={20} /></button>
                                                    </div>
                                                    <div className="p-4 flex gap-6 border-b border-slate-800">
                                                        <span className="text-white font-medium border-b-2 border-[#22c55e] pb-2 -mb-[18px]">Inputs & Style</span>
                                                    </div>
                                                    <div className="p-6 space-y-4">
                                                        {allIndicatorsList.flatMap(c => c.items).find(i => i.key === settingsModal)?.fields.map(field => (
                                                            <div key={field.name} className="flex justify-between items-center">
                                                                <span className="text-slate-400 text-sm">{field.label}</span>
                                                                <input
                                                                    type="number"
                                                                    value={tempSettings[field.name]}
                                                                    onChange={(e) => setTempSettings({ ...tempSettings, [field.name]: parseFloat(e.target.value) || 1 })}
                                                                    className="w-24 bg-slate-900 border border-slate-700 text-white rounded px-3 py-1.5 focus:border-[#22c55e] outline-none text-right"
                                                                />
                                                            </div>
                                                        ))}

                                                        {indicatorConfig[settingsModal]?.color && (
                                                            <div className="flex justify-between items-center">
                                                                <span className="text-slate-400 text-sm">Color</span>
                                                                <input
                                                                    type="color"
                                                                    value={tempSettings.color || '#3b82f6'}
                                                                    onChange={(e) => setTempSettings({ ...tempSettings, color: e.target.value })}
                                                                    className="w-10 h-10 p-1 bg-transparent border-0 cursor-pointer"
                                                                />
                                                            </div>
                                                        )}
                                                    </div>
                                                    <div className="p-4 border-t border-[#333333] flex justify-end gap-3">
                                                        <button onClick={() => setSettingsModal(null)} className="px-4 py-2 rounded-lg border border-[#333333] text-slate-300 hover:bg-[#333333] transition-colors text-sm font-medium">Cancel</button>
                                                        <button onClick={() => { updateIndicatorSettings(settingsModal, 'all', tempSettings); setSettingsModal(null); }} className="px-5 py-2 rounded-lg bg-[#22c55e] hover:bg-[#16a34a] text-white transition-colors text-sm font-medium">Ok</button>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* Chart Component */}
                            <div className="relative">
                                {loadingChart && (
                                    <div className="absolute inset-0 z-10 flex items-center justify-center bg-[#050505]/50 backdrop-blur-sm rounded-2xl">
                                        <div className="flex flex-col items-center gap-3">
                                            <div className="w-8 h-8 border-4 border-[#22c55e] border-t-transparent rounded-full animate-spin"></div>
                                            <span className="text-slate-300 font-medium">Loading Chart Data...</span>
                                        </div>
                                    </div>
                                )}
                                <StockChart data={chartData} symbol={selectedStock.symbol} indicators={indicatorConfig} interval={interval} chartType={chartType} onOpenSettings={(key) => { setTempSettings({ key, ...indicatorConfig[key] }); setSettingsModal(key); }} />
                            </div>
                        </div>

                        {/* Sidebar (Trade + Portfolio) */}
                        <div className="space-y-6">

                            {/* Order Panel */}
                            <div className="bg-white/[0.02] border border-white/5 p-4 sm:p-6 rounded-2xl sm:rounded-3xl shadow-2xl backdrop-blur-xl relative overflow-hidden group hover:border-white/10 transition-colors">
                                <div className="absolute top-0 right-0 w-32 h-32 bg-[#22c55e]/5 blur-[60px] rounded-full pointer-events-none group-hover:bg-[#22c55e]/10 transition-colors" />
                                <div className="flex items-center justify-between mb-6">
                                    <h3 className="text-xl font-bold flex items-center gap-2 text-white">
                                        <ArrowRightLeft size={20} className="text-[#22c55e]" /> Place Order
                                    </h3>
                                    <div className="text-sm px-3 py-1 bg-slate-800 rounded-full font-mono font-medium text-slate-300">
                                        {selectedStock.exchange.replace('_EQ', '')} EQ
                                    </div>
                                </div>

                                <div className="space-y-5">
                                    <div className="space-y-4">
                                        <label className="text-xs font-bold text-slate-400 uppercase tracking-wider block px-1">Quantity (Units)</label>
                                        <div className="flex items-center border border-[#333333] rounded-xl overflow-hidden bg-[#050505] focus-within:border-slate-500/50 transition-colors w-full h-12">
                                            <button
                                                onClick={() => setQty(Math.max(1, qty - 1))}
                                                className="w-10 ml-1.5 my-1.5 rounded-lg hover:bg-slate-700/50 font-black text-slate-300 flex items-center justify-center transition-colors bg-slate-800/80 cursor-pointer h-9 shrink-0"
                                            >
                                                -
                                            </button>
                                            <input
                                                type="number"
                                                min="1"
                                                value={qty}
                                                onChange={(e) => setQty(parseInt(e.target.value) || 1)}
                                                className="flex-1 bg-transparent text-center h-full text-lg font-bold text-white focus:outline-none placeholder-slate-600 outline-none w-full [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                            />
                                            <button
                                                onClick={() => setQty(qty + 1)}
                                                className="w-10 mr-1.5 my-1.5 rounded-lg hover:bg-slate-700/50 font-black text-slate-300 flex items-center justify-center transition-colors bg-white/10 cursor-pointer h-9 shrink-0"
                                            >
                                                +
                                            </button>
                                        </div>
                                    </div>

                                    <div className="flex justify-between items-center px-1">
                                        <span className="text-slate-400 text-sm font-medium">Est. Cost</span>
                                        <span className="text-white font-mono font-bold text-lg">₹{((ltp || 0) * qty).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>
                                    </div>

                                    <div className="grid grid-cols-2 gap-3 pt-2">
                                        <button
                                            onClick={() => handleTrade('BUY')}
                                            disabled={!ltp}
                                            className="bg-white hover:bg-gray-200 text-black disabled:bg-white/5 disabled:text-white/20 font-black py-4 rounded-2xl transition-all uppercase tracking-widest text-sm shadow-[0_0_20px_rgba(255,255,255,0.1)] active:scale-95"
                                        >
                                            Buy
                                        </button>
                                        <button
                                            onClick={() => handleTrade('SELL')}
                                            disabled={!ltp || !currentPosition || currentPosition.qty < qty}
                                            className="bg-red-500/10 hover:bg-red-500/20 disabled:bg-white/5 disabled:text-white/20 text-red-500 font-black py-4 rounded-2xl transition-all uppercase tracking-widest text-sm border border-red-500/20 hover:border-red-500/30 active:scale-95"
                                        >
                                            Sell
                                        </button>
                                    </div>
                                </div>
                            </div>

                            {/* Portfolio Panel */}
                            <div className="bg-white/[0.02] border border-white/5 p-4 sm:p-6 rounded-2xl sm:rounded-3xl shadow-2xl backdrop-blur-xl flex flex-col max-h-[400px] hover:border-white/10 transition-colors">
                                <h3 className="text-xl font-bold mb-6 flex items-center gap-2 text-white shrink-0">
                                    <Briefcase size={20} className="text-[#22c55e]" /> My Portfolio
                                </h3>

                                <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
                                    {Object.keys(positions).length === 0 ? (
                                        <div className="flex flex-col justify-center items-center text-slate-500 gap-3 py-8">
                                            <Briefcase size={32} className="opacity-20" />
                                            <span className="text-sm font-medium">No active positions</span>
                                        </div>
                                    ) : (
                                        <div className="space-y-4">
                                            {Object.values(positions).map(pos => {
                                                const isCurrent = pos.symbol === selectedStock.symbol;
                                                const posLtp = isCurrent && ltp ? ltp : pos.avgPrice; // using avg price if not selected to avoid making 10 api calls for demo
                                                const pnl = (posLtp - pos.avgPrice) * pos.qty;
                                                const isProfit = pnl >= 0;

                                                return (
                                                    <div key={pos.symbol} className="bg-slate-800/40 border border-slate-700/50 p-4 rounded-xl">
                                                        <div className="flex justify-between items-start mb-2">
                                                            <span className="font-bold text-white">{pos.symbol} <span className="text-xs bg-slate-700/50 text-slate-300 px-1.5 py-0.5 rounded ml-1">x{pos.qty}</span></span>
                                                            <span className={`text-sm font-bold font-mono ${isProfit ? 'text-[#22c55e]' : 'text-red-500'}`}>
                                                                {isProfit ? '+' : ''}₹{pnl.toFixed(2)}
                                                            </span>
                                                        </div>
                                                        <div className="flex justify-between text-xs text-slate-400">
                                                            <span>Avg: ₹{pos.avgPrice.toFixed(2)}</span>
                                                            <span>{isCurrent ? `LTP: ₹${posLtp.toFixed(2)}` : 'Switch to view LTP'}</span>
                                                        </div>
                                                    </div>
                                                )
                                            })}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center py-[20vh] border border-white/5 rounded-3xl bg-white/[0.01] backdrop-blur-xl shadow-2xl relative overflow-hidden group">
                        <div className="absolute inset-0 bg-gradient-to-b from-[#22c55e]/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-1000" />
                        <div className="bg-white/[0.02] border border-white/5 p-8 rounded-3xl mb-6 shadow-xl relative z-10 group-hover:scale-110 transition-transform duration-700">
                            <TrendingUp size={48} className="text-[#22c55e] drop-shadow-[0_0_15px_rgba(34,197,94,0.4)]" />
                        </div>
                        <h2 className="text-3xl font-black tracking-tight text-white mb-3">Commodities Engine Ready</h2>
                        <p className="text-white/40 max-w-md text-center text-sm">Select a commodity from the list above to view real-time data feeds, institutional indicators, and execute paper trades.</p>
                    </div>
                )}
            </div>

            {/* Trade Journal */}
            <TradeHistory />
        </div>
    );
};

export default DemoCommoditiesTrading;
