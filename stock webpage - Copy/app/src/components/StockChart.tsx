import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, LineSeries, CandlestickSeries, HistogramSeries } from 'lightweight-charts';
import type { ISeriesApi } from 'lightweight-charts';
import { SMA, EMA, RSI, MACD, BollingerBands, VWAP, Stochastic, ATR, ADX, IchimokuCloud, OBV, CCI, WilliamsR, MFI, KeltnerChannels } from 'technicalindicators';
import { Settings } from 'lucide-react';

interface StockChartProps {
    data: any[];
    symbol: string;
    interval: string;
    indicators: any;
    chartType?: 'candle' | 'line';
    onOpenSettings?: (key: string) => void;
}

const StockChart: React.FC<StockChartProps> = ({ data, symbol, interval, indicators, chartType = 'candle', onOpenSettings }) => {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<any>(null);
    const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
    const priceLineRef = useRef<ISeriesApi<"Line"> | null>(null);
    const smaSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
    const emaSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
    const bbUpperRef = useRef<ISeriesApi<"Line"> | null>(null);
    const bbLowerRef = useRef<ISeriesApi<"Line"> | null>(null);
    const rsiRef = useRef<ISeriesApi<"Line"> | null>(null);
    const macdRef = useRef<ISeriesApi<"Line"> | null>(null);
    const macdSignalRef = useRef<ISeriesApi<"Line"> | null>(null);
    const vwapRef = useRef<ISeriesApi<"Line"> | null>(null);
    const stochKRef = useRef<ISeriesApi<"Line"> | null>(null);
    const stochDRef = useRef<ISeriesApi<"Line"> | null>(null);
    const atrRef = useRef<ISeriesApi<"Line"> | null>(null);
    const adxRef = useRef<ISeriesApi<"Line"> | null>(null);
    const obvRef = useRef<ISeriesApi<"Line"> | null>(null);
    const cciRef = useRef<ISeriesApi<"Line"> | null>(null);
    const williamsRef = useRef<ISeriesApi<"Line"> | null>(null);
    const mfiRef = useRef<ISeriesApi<"Line"> | null>(null);
    const kcUpperRef = useRef<ISeriesApi<"Line"> | null>(null);
    const kcLowerRef = useRef<ISeriesApi<"Line"> | null>(null);
    const ichimokuConversionRef = useRef<ISeriesApi<"Line"> | null>(null);
    const ichimokuBaseRef = useRef<ISeriesApi<"Line"> | null>(null);
    const ichimokuSpanARef = useRef<ISeriesApi<"Line"> | null>(null);
    const ichimokuSpanBRef = useRef<ISeriesApi<"Line"> | null>(null);
    const volumeRef = useRef<any>(null);

    useEffect(() => {
        if (!chartContainerRef.current) return;
        const chart = createChart(chartContainerRef.current, {
            layout: { background: { type: ColorType.Solid, color: '#0f172a' }, textColor: '#94a3b8' },
            grid: { vertLines: { color: '#1e293b' }, horzLines: { color: '#1e293b' } },
            width: chartContainerRef.current.clientWidth,
            height: window.innerWidth < 768 ? 350 : 540,
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
                tickMarkFormatter: (time: number, tickMarkType: any) => {
                    const dt = new Date(time * 1000);
                    // Lightweight Charts TickMarkType: 0 = Year, 1 = Month, 2 = DayOfMonth, 3 = Time, 4 = TimeWithSeconds
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
            crosshair: { mode: 1 },
            leftPriceScale: { visible: true, borderColor: '#1e293b' },
            rightPriceScale: { visible: true, borderColor: '#1e293b' },
        });

        const series = chart.addSeries(CandlestickSeries, {
            upColor: '#22c55e',
            downColor: '#ef4444',
            borderVisible: false,
            wickUpColor: '#22c55e',
            wickDownColor: '#ef4444',
        });

        const priceLine = chart.addSeries(LineSeries, {
            color: '#3b82f6',
            lineWidth: 2,
            crosshairMarkerVisible: true,
        });

        const smaSeries = chart.addSeries(LineSeries, { color: '#22c55e', lineWidth: 2, crosshairMarkerVisible: false }); // Green
        const emaSeries = chart.addSeries(LineSeries, { color: '#f59e0b', lineWidth: 2, crosshairMarkerVisible: false }); // Amber
        const vwapSeries = chart.addSeries(LineSeries, { color: '#eab308', lineWidth: 2, crosshairMarkerVisible: false }); // Yellow
        const bbUpper = chart.addSeries(LineSeries, { color: '#06b6d4', lineWidth: 1, lineStyle: 2, crosshairMarkerVisible: false });
        const bbLower = chart.addSeries(LineSeries, { color: '#06b6d4', lineWidth: 1, lineStyle: 2, crosshairMarkerVisible: false });

        // Oscillators on left scale
        const rsi = chart.addSeries(LineSeries, { color: '#a855f7', lineWidth: 2, priceScaleId: 'left', crosshairMarkerVisible: false });
        const macdLine = chart.addSeries(LineSeries, { color: '#fb7185', lineWidth: 2, priceScaleId: 'left', crosshairMarkerVisible: false });
        const macdSignal = chart.addSeries(LineSeries, { color: '#94a3b8', lineWidth: 1, priceScaleId: 'left', crosshairMarkerVisible: false });
        const stochK = chart.addSeries(LineSeries, { color: '#10b981', lineWidth: 2, priceScaleId: 'left', crosshairMarkerVisible: false });
        const stochD = chart.addSeries(LineSeries, { color: '#f43f5e', lineWidth: 2, lineStyle: 2, priceScaleId: 'left', crosshairMarkerVisible: false });
        const atr = chart.addSeries(LineSeries, { color: '#8b5cf6', lineWidth: 2, priceScaleId: 'left', crosshairMarkerVisible: false });
        const adx = chart.addSeries(LineSeries, { color: '#f97316', lineWidth: 2, priceScaleId: 'left', crosshairMarkerVisible: false });
        const cci = chart.addSeries(LineSeries, { color: '#ec4899', lineWidth: 2, priceScaleId: 'left', crosshairMarkerVisible: false });
        const williamsR = chart.addSeries(LineSeries, { color: '#0ea5e9', lineWidth: 2, priceScaleId: 'left', crosshairMarkerVisible: false });
        const mfi = chart.addSeries(LineSeries, { color: '#14b8a6', lineWidth: 2, priceScaleId: 'left', crosshairMarkerVisible: false });

        const kcUpper = chart.addSeries(LineSeries, { color: '#8b5cf6', lineWidth: 1, lineStyle: 2, crosshairMarkerVisible: false });
        const kcLower = chart.addSeries(LineSeries, { color: '#8b5cf6', lineWidth: 1, lineStyle: 2, crosshairMarkerVisible: false });

        const ichiConv = chart.addSeries(LineSeries, { color: '#14b8a6', lineWidth: 2, crosshairMarkerVisible: false });
        const ichiBase = chart.addSeries(LineSeries, { color: '#0ea5e9', lineWidth: 2, crosshairMarkerVisible: false });
        const ichiSpanA = chart.addSeries(LineSeries, { color: 'rgba(34, 197, 94, 0.35)', lineWidth: 3, crosshairMarkerVisible: false });
        const ichiSpanB = chart.addSeries(LineSeries, { color: 'rgba(239, 68, 68, 0.35)', lineWidth: 3, crosshairMarkerVisible: false });

        const volume = chart.addSeries(HistogramSeries, { color: '#64748b', priceFormat: { type: 'volume' }, priceScaleId: '' });
        chart.priceScale('').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
        const obv = chart.addSeries(LineSeries, { color: '#3b82f6', lineWidth: 2, priceScaleId: 'left', crosshairMarkerVisible: false });

        chartRef.current = chart;
        seriesRef.current = series;
        priceLineRef.current = priceLine;
        smaSeriesRef.current = smaSeries;
        emaSeriesRef.current = emaSeries;
        vwapRef.current = vwapSeries;
        bbUpperRef.current = bbUpper;
        bbLowerRef.current = bbLower;
        rsiRef.current = rsi;
        macdRef.current = macdLine;
        macdSignalRef.current = macdSignal;
        stochKRef.current = stochK;
        stochDRef.current = stochD;
        atrRef.current = atr;
        adxRef.current = adx;
        cciRef.current = cci;
        williamsRef.current = williamsR;
        mfiRef.current = mfi;
        kcUpperRef.current = kcUpper;
        kcLowerRef.current = kcLower;
        ichimokuConversionRef.current = ichiConv;
        ichimokuBaseRef.current = ichiBase;
        ichimokuSpanARef.current = ichiSpanA;
        ichimokuSpanBRef.current = ichiSpanB;
        volumeRef.current = volume;
        obvRef.current = obv;

        const resize = () => {
            if (chartContainerRef.current) {
                chart.applyOptions({
                    width: chartContainerRef.current.clientWidth,
                    height: window.innerWidth < 768 ? 350 : 540
                });
            }
        };
        window.addEventListener('resize', resize);
        return () => { window.removeEventListener('resize', resize); chart.remove(); };
    }, []);

    useEffect(() => {
        if (!seriesRef.current || data.length === 0) return;

        // Sort data to ensure chronological order and verify it
        const sortedData = [...data].sort((a, b) => (a.time as number) - (b.time as number));

        // Validate unique times to prevent lightweight-charts error
        const uniqueMap = new Map();
        for (const d of sortedData) {
            if (!uniqueMap.has(d.time)) uniqueMap.set(d.time, d);
        }
        const cleanData = Array.from(uniqueMap.values());

        seriesRef.current.setData(cleanData);
        if (priceLineRef.current) {
            priceLineRef.current.setData(cleanData.map(d => ({ time: d.time, value: d.close })));
        }

        if (chartType === 'line') {
            seriesRef.current.applyOptions({ visible: false });
            if (priceLineRef.current) priceLineRef.current.applyOptions({ visible: true });
        } else {
            seriesRef.current.applyOptions({ visible: true });
            if (priceLineRef.current) priceLineRef.current.applyOptions({ visible: false });
        }

        const closePrices = cleanData.map(d => d.close);
        const highPrices = cleanData.map(d => d.high);
        const lowPrices = cleanData.map(d => d.low);
        const volumes = cleanData.map(d => d.volume !== undefined ? d.volume : 0);

        const safeMap = (rawData: any[], vExtractor: (d: any) => number) => {
            const valid = rawData.map(d => ({ v: vExtractor(d), orig: d }))
                .filter(d => typeof d.v === 'number' && !Number.isNaN(d.v));
            const offset = cleanData.length - valid.length;
            if (offset < 0) return []; // Should never happen unless indicator returns MORE than input
            return valid.map((d, idx) => ({ time: cleanData[idx + offset].time, value: d.v }));
        };

        // Volume
        if (indicators.volume?.enabled && volumeRef.current) {
            volumeRef.current.setData(cleanData.map(d => ({ time: d.time, value: d.volume, color: d.close >= d.open ? '#22c55e80' : '#ef444480' })));
        } else { volumeRef.current?.setData([]); }

        // SMA
        if (indicators.sma?.enabled && smaSeriesRef.current) {
            smaSeriesRef.current.setData(safeMap(SMA.calculate({ period: indicators.sma.period, values: closePrices }), v => v));
            smaSeriesRef.current.applyOptions({ color: indicators.sma.color });
        } else { smaSeriesRef.current?.setData([]); }

        // EMA
        if (indicators.ema?.enabled && emaSeriesRef.current) {
            emaSeriesRef.current.setData(safeMap(EMA.calculate({ period: indicators.ema.period, values: closePrices }), v => v));
            emaSeriesRef.current.applyOptions({ color: indicators.ema.color });
        } else { emaSeriesRef.current?.setData([]); }

        // VWAP
        if (indicators.vwap?.enabled && vwapRef.current) {
            vwapRef.current.setData(safeMap(VWAP.calculate({ high: highPrices, low: lowPrices, close: closePrices, volume: volumes }), v => v));
            vwapRef.current.applyOptions({ color: indicators.vwap.color });
        } else { vwapRef.current?.setData([]); }

        // Bollinger Bands (20, 2)
        if (indicators.bb?.enabled && bbUpperRef.current && bbLowerRef.current) {
            const bbData = BollingerBands.calculate({ period: indicators.bb.period, values: closePrices, stdDev: indicators.bb.stdDev });
            bbUpperRef.current.setData(safeMap(bbData, v => v.upper));
            bbLowerRef.current.setData(safeMap(bbData, v => v.lower));
            bbUpperRef.current.applyOptions({ color: indicators.bb.color });
            bbLowerRef.current.applyOptions({ color: indicators.bb.color });
        } else { bbUpperRef.current?.setData([]); bbLowerRef.current?.setData([]); }

        // RSI 14
        if (indicators.rsi?.enabled && rsiRef.current) {
            rsiRef.current.setData(safeMap(RSI.calculate({ period: indicators.rsi.period, values: closePrices }), v => v));
            rsiRef.current.applyOptions({ color: indicators.rsi.color });
        } else { rsiRef.current?.setData([]); }

        // MACD
        if (indicators.macd?.enabled && macdRef.current && macdSignalRef.current) {
            const macdData = MACD.calculate({ values: closePrices, fastPeriod: indicators.macd.fast, slowPeriod: indicators.macd.slow, signalPeriod: indicators.macd.signal, SimpleMAOscillator: false, SimpleMASignal: false });
            macdRef.current.setData(safeMap(macdData, v => v.MACD));
            macdSignalRef.current.setData(safeMap(macdData, v => v.signal));
            macdRef.current.applyOptions({ color: indicators.macd.color });
            macdSignalRef.current.applyOptions({ color: indicators.macd.color + '80' });
        } else { macdRef.current?.setData([]); macdSignalRef.current?.setData([]); }

        // Stochastic (14, 3, 3)
        if (indicators.stoch?.enabled && stochKRef.current && stochDRef.current) {
            const stochData = Stochastic.calculate({ high: highPrices, low: lowPrices, close: closePrices, period: indicators.stoch.period, signalPeriod: indicators.stoch.signal });
            stochKRef.current.setData(safeMap(stochData, v => v.k));
            stochDRef.current.setData(safeMap(stochData, v => v.d));
            stochKRef.current.applyOptions({ color: indicators.stoch.color });
            stochDRef.current.applyOptions({ color: indicators.stoch.color + '80' });
        } else { stochKRef.current?.setData([]); stochDRef.current?.setData([]); }

        // ATR 14
        if (indicators.atr?.enabled && atrRef.current) {
            atrRef.current.setData(safeMap(ATR.calculate({ high: highPrices, low: lowPrices, close: closePrices, period: indicators.atr.period }), v => v));
            atrRef.current.applyOptions({ color: indicators.atr.color });
        } else { atrRef.current?.setData([]); }

        // ADX 14
        if (indicators.adx?.enabled && adxRef.current) {
            adxRef.current.setData(safeMap(ADX.calculate({ high: highPrices, low: lowPrices, close: closePrices, period: indicators.adx.period }), v => v.adx));
            adxRef.current.applyOptions({ color: indicators.adx.color });
        } else { adxRef.current?.setData([]); }

        // OBV
        if (indicators.obv?.enabled && obvRef.current) {
            obvRef.current.setData(safeMap(OBV.calculate({ close: closePrices, volume: volumes }), v => v));
            obvRef.current.applyOptions({ color: indicators.obv.color });
        } else { obvRef.current?.setData([]); }

        // CCI
        if (indicators.cci?.enabled && cciRef.current) {
            cciRef.current.setData(safeMap(CCI.calculate({ high: highPrices, low: lowPrices, close: closePrices, period: indicators.cci.period }), v => v));
            cciRef.current.applyOptions({ color: indicators.cci.color });
        } else { cciRef.current?.setData([]); }

        // Williams %R
        if (indicators.williamsr?.enabled && williamsRef.current) {
            williamsRef.current.setData(safeMap(WilliamsR.calculate({ high: highPrices, low: lowPrices, close: closePrices, period: indicators.williamsr.period }), v => v));
            williamsRef.current.applyOptions({ color: indicators.williamsr.color });
        } else { williamsRef.current?.setData([]); }

        // MFI
        if (indicators.mfi?.enabled && mfiRef.current) {
            mfiRef.current.setData(safeMap(MFI.calculate({ high: highPrices, low: lowPrices, close: closePrices, volume: volumes, period: indicators.mfi.period }), v => v));
            mfiRef.current.applyOptions({ color: indicators.mfi.color });
        } else { mfiRef.current?.setData([]); }

        // Keltner Channels
        if (indicators.kc?.enabled && kcUpperRef.current && kcLowerRef.current) {
            const kcData = KeltnerChannels.calculate({ high: highPrices, low: lowPrices, close: closePrices, maPeriod: indicators.kc.period, atrPeriod: indicators.kc.period, useSMA: false, multiplier: indicators.kc.multiplier });
            kcUpperRef.current.setData(safeMap(kcData, v => v.upper));
            kcLowerRef.current.setData(safeMap(kcData, v => v.lower));
            kcUpperRef.current.applyOptions({ color: indicators.kc.color });
            kcLowerRef.current.applyOptions({ color: indicators.kc.color });
        } else { kcUpperRef.current?.setData([]); kcLowerRef.current?.setData([]); }

        // Ichimoku
        if (indicators.ichimoku?.enabled && ichimokuConversionRef.current && ichimokuBaseRef.current && ichimokuSpanARef.current && ichimokuSpanBRef.current) {
            const disp = indicators.ichimoku.displacement;
            const ichiData = IchimokuCloud.calculate({ high: highPrices, low: lowPrices, conversionPeriod: indicators.ichimoku.conversion, basePeriod: indicators.ichimoku.base, spanPeriod: indicators.ichimoku.span, displacement: disp });
            ichimokuConversionRef.current.setData(safeMap(ichiData, v => v.conversion));
            ichimokuBaseRef.current.setData(safeMap(ichiData, v => v.base));

            let intervalSeconds = 60;
            if (interval === '5m') intervalSeconds = 300;
            if (interval === '15m') intervalSeconds = 900;
            if (interval === '30m') intervalSeconds = 1800;
            if (interval === '1h') intervalSeconds = 3600;
            if (interval === '1d') intervalSeconds = 86400;
            if (interval === '1wk') intervalSeconds = 604800;
            if (interval === '1mo') intervalSeconds = 2592000;

            const shiftMap = (rawData: any[], vExtractor: (d: any) => number, shiftPeriods: number) => {
                const valid = rawData.map(d => ({ v: vExtractor(d) })).filter(d => typeof d.v === 'number' && !Number.isNaN(d.v));
                const offset = cleanData.length - valid.length;
                if (offset < 0) return [];
                return valid.map((d, idx) => {
                    const baseTime = cleanData[idx + offset].time as number;
                    return { time: (baseTime + shiftPeriods * intervalSeconds) as import('lightweight-charts').Time, value: d.v };
                });
            };

            ichimokuSpanARef.current.setData(shiftMap(ichiData, v => v.spanA, disp));
            ichimokuSpanBRef.current.setData(shiftMap(ichiData, v => v.spanB, disp));
            ichimokuConversionRef.current.applyOptions({ color: indicators.ichimoku.color });
        } else {
            ichimokuConversionRef.current?.setData([]);
            ichimokuBaseRef.current?.setData([]);
            ichimokuSpanARef.current?.setData([]);
            ichimokuSpanBRef.current?.setData([]);
        }

        if (cleanData.length > 0) {
            // Only fit content on initial load or full data swaps to allow users to scroll freely while LIVE data injects
            if (!chartContainerRef.current?.dataset.lastRange || chartContainerRef.current?.dataset.lastSymbol !== symbol || chartContainerRef.current?.dataset.lastInterval !== interval) {
                chartRef.current?.timeScale().fitContent();
                if (chartContainerRef.current) {
                    chartContainerRef.current.dataset.lastSymbol = symbol;
                    chartContainerRef.current.dataset.lastInterval = interval;
                    chartContainerRef.current.dataset.lastRange = 'true';
                }
            }
        }

    }, [data, indicators, chartType]);

    return (
        <div className="w-full bg-slate-900 border border-slate-800 rounded-2xl shadow-xl overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
                <h2 className="text-xl font-bold text-white flex items-center gap-3">
                    {symbol} <span className="text-xs font-normal px-2 py-1 bg-slate-800 text-slate-400 rounded uppercase">{interval} timeframe</span>
                </h2>
            </div>
            <div className="w-full relative touch-none">
                <div ref={chartContainerRef} className="w-full h-full" />
                <div className="absolute top-4 left-4 z-[5] pointer-events-auto flex flex-col gap-1.5 bg-slate-900/40 p-2 rounded backdrop-blur-sm border border-slate-700/50">
                    <div className="text-xs font-bold text-slate-300">Active Indicators</div>
                    {indicators.sma?.enabled && <div className="flex items-center gap-2 group cursor-pointer" onClick={() => onOpenSettings && onOpenSettings('sma')}><div className="w-3 h-0.5 rounded-full" style={{ backgroundColor: indicators.sma.color }}></div><span className="text-xs font-medium text-slate-300 group-hover:text-[#22c55e] transition-colors">SMA {indicators.sma.period}</span><Settings size={12} className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" /></div>}
                    {indicators.ema?.enabled && <div className="flex items-center gap-2 group cursor-pointer" onClick={() => onOpenSettings && onOpenSettings('ema')}><div className="w-3 h-0.5 rounded-full" style={{ backgroundColor: indicators.ema.color }}></div><span className="text-xs font-medium text-slate-300 group-hover:text-amber-400 transition-colors">EMA {indicators.ema.period}</span><Settings size={12} className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" /></div>}
                    {indicators.vwap?.enabled && <div className="flex items-center gap-2 group cursor-pointer" onClick={() => onOpenSettings && onOpenSettings('vwap')}><div className="w-3 h-0.5 rounded-full" style={{ backgroundColor: indicators.vwap.color }}></div><span className="text-xs font-medium text-slate-300 group-hover:text-yellow-400 transition-colors">VWAP</span><Settings size={12} className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" /></div>}
                    {indicators.bb?.enabled && <div className="flex items-center gap-2 group cursor-pointer" onClick={() => onOpenSettings && onOpenSettings('bb')}><div className="w-3 h-0.5 border-t border-dashed" style={{ borderColor: indicators.bb.color }}></div><span className="text-xs font-medium text-slate-300 group-hover:text-cyan-400 transition-colors">BB {indicators.bb.period}</span><Settings size={12} className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" /></div>}
                    {indicators.kc?.enabled && <div className="flex items-center gap-2 group cursor-pointer" onClick={() => onOpenSettings && onOpenSettings('kc')}><div className="w-3 h-0.5 border-t border-dashed" style={{ borderColor: indicators.kc.color }}></div><span className="text-xs font-medium text-slate-300 group-hover:text-purple-400 transition-colors">KC {indicators.kc.period}</span><Settings size={12} className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" /></div>}
                    {indicators.ichimoku?.enabled && <div className="flex items-center gap-2 group cursor-pointer" onClick={() => onOpenSettings && onOpenSettings('ichimoku')}><div className="w-3 h-0.5 rounded-full" style={{ backgroundColor: indicators.ichimoku.color }}></div><span className="text-xs font-medium text-slate-300 group-hover:text-teal-400 transition-colors">Ichimoku</span><Settings size={12} className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" /></div>}
                    {indicators.volume?.enabled && <div className="flex items-center gap-2 group cursor-pointer" onClick={() => onOpenSettings && onOpenSettings('volume')}><div className="w-3 h-2 rounded-sm" style={{ backgroundColor: indicators.volume.color }}></div><span className="text-xs font-medium text-slate-300 group-hover:text-slate-100 transition-colors">Vol</span><Settings size={12} className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" /></div>}
                    {indicators.rsi?.enabled && <div className="flex items-center gap-2 group cursor-pointer" onClick={() => onOpenSettings && onOpenSettings('rsi')}><div className="w-3 h-0.5 rounded-full" style={{ backgroundColor: indicators.rsi.color }}></div><span className="text-xs font-medium text-slate-300 group-hover:text-purple-400 transition-colors">RSI {indicators.rsi.period}</span><Settings size={12} className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" /></div>}
                    {indicators.macd?.enabled && <div className="flex items-center gap-2 group cursor-pointer" onClick={() => onOpenSettings && onOpenSettings('macd')}><div className="w-3 h-0.5 rounded-full" style={{ backgroundColor: indicators.macd.color }}></div><span className="text-xs font-medium text-slate-300 group-hover:text-rose-400 transition-colors">MACD {indicators.macd.fast},{indicators.macd.slow}</span><Settings size={12} className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" /></div>}
                    {indicators.stoch?.enabled && <div className="flex items-center gap-2 group cursor-pointer" onClick={() => onOpenSettings && onOpenSettings('stoch')}><div className="w-3 h-0.5 rounded-full" style={{ backgroundColor: indicators.stoch.color }}></div><span className="text-xs font-medium text-slate-300 group-hover:text-emerald-400 transition-colors">Stoch {indicators.stoch.period}</span><Settings size={12} className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" /></div>}
                    {indicators.atr?.enabled && <div className="flex items-center gap-2 group cursor-pointer" onClick={() => onOpenSettings && onOpenSettings('atr')}><div className="w-3 h-0.5 rounded-full" style={{ backgroundColor: indicators.atr.color }}></div><span className="text-xs font-medium text-slate-300 group-hover:text-emerald-400 transition-colors">ATR {indicators.atr.period}</span><Settings size={12} className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" /></div>}
                    {indicators.adx?.enabled && <div className="flex items-center gap-2 group cursor-pointer" onClick={() => onOpenSettings && onOpenSettings('adx')}><div className="w-3 h-0.5 rounded-full" style={{ backgroundColor: indicators.adx.color }}></div><span className="text-xs font-medium text-slate-300 group-hover:text-orange-400 transition-colors">ADX {indicators.adx.period}</span><Settings size={12} className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" /></div>}
                    {indicators.obv?.enabled && <div className="flex items-center gap-2 group cursor-pointer" onClick={() => onOpenSettings && onOpenSettings('obv')}><div className="w-3 h-0.5 rounded-full" style={{ backgroundColor: indicators.obv.color }}></div><span className="text-xs font-medium text-slate-300 group-hover:text-[#22c55e] transition-colors">OBV</span><Settings size={12} className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" /></div>}
                    {indicators.cci?.enabled && <div className="flex items-center gap-2 group cursor-pointer" onClick={() => onOpenSettings && onOpenSettings('cci')}><div className="w-3 h-0.5 rounded-full" style={{ backgroundColor: indicators.cci.color }}></div><span className="text-xs font-medium text-slate-300 group-hover:text-pink-400 transition-colors">CCI {indicators.cci.period}</span><Settings size={12} className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" /></div>}
                    {indicators.williamsr?.enabled && <div className="flex items-center gap-2 group cursor-pointer" onClick={() => onOpenSettings && onOpenSettings('williamsr')}><div className="w-3 h-0.5 rounded-full" style={{ backgroundColor: indicators.williamsr.color }}></div><span className="text-xs font-medium text-slate-300 group-hover:text-sky-400 transition-colors">Williams %R {indicators.williamsr.period}</span><Settings size={12} className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" /></div>}
                    {indicators.mfi?.enabled && <div className="flex items-center gap-2 group cursor-pointer" onClick={() => onOpenSettings && onOpenSettings('mfi')}><div className="w-3 h-0.5 rounded-full" style={{ backgroundColor: indicators.mfi.color }}></div><span className="text-xs font-medium text-slate-300 group-hover:text-teal-400 transition-colors">MFI {indicators.mfi.period}</span><Settings size={12} className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" /></div>}
                </div>
            </div>
        </div>
    );
};

export default StockChart;
