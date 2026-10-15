import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi, ISeriesApi, LineStyle } from 'lightweight-charts';

interface OHLCV {
    time: string; // YYYY-MM-DD
    open: number;
    high: number;
    low: number;
    close: number;
    value: number; // Volume
}

interface ChartAnnotation {
    type: 'support' | 'resistance' | 'pivot' | 'swing_high' | 'swing_low';
    price: number;
    time: string;
    text?: string;
    color?: string;
}

interface ResearchChartProps {
    data: OHLCV[];
    annotations?: ChartAnnotation[];
}

export const ResearchChart: React.FC<ResearchChartProps> = ({ data, annotations = [] }) => {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

    useEffect(() => {
        if (!chartContainerRef.current) return;

        // Initialize chart
        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { color: '#1e293b' }, // Tailwind slate-800
                textColor: '#94a3b8',
            },
            grid: {
                vertLines: { color: '#334155' },
                horzLines: { color: '#334155' },
            },
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
            },
            width: chartContainerRef.current.clientWidth,
            height: 400,
        });

        chartRef.current = chart;

        // Add Candlestick series
        const candlestickSeries = chart.addCandlestickSeries({
            upColor: '#22c55e',
            downColor: '#ef4444',
            borderVisible: false,
            wickUpColor: '#22c55e',
            wickDownColor: '#ef4444',
        });
        candlestickSeriesRef.current = candlestickSeries;

        // Add Volume series
        const volumeSeries = chart.addHistogramSeries({
            color: '#3b82f6',
            priceFormat: {
                type: 'volume',
            },
            priceScaleId: '', // set as an overlay
        });
        volumeSeries.priceScale().applyOptions({
            scaleMargins: {
                top: 0.8,
                bottom: 0,
            },
        });

        if (data.length > 0) {
            candlestickSeries.setData(data);
            volumeSeries.setData(data.map(d => ({
                time: d.time,
                value: d.value,
                color: d.close >= d.open ? 'rgba(34, 197, 94, 0.5)' : 'rgba(239, 68, 68, 0.5)'
            })));
        }

        // Apply Annotations (Price lines and markers)
        const markers: any[] = [];
        
        annotations.forEach(ann => {
            if (ann.type === 'support' || ann.type === 'resistance' || ann.type === 'pivot') {
                const color = ann.type === 'support' ? '#22c55e' : (ann.type === 'resistance' ? '#ef4444' : '#eab308');
                candlestickSeries.createPriceLine({
                    price: ann.price,
                    color: color,
                    lineWidth: 2,
                    lineStyle: LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: ann.text || ann.type.toUpperCase(),
                });
            } else if (ann.type === 'swing_high' || ann.type === 'swing_low') {
                markers.push({
                    time: ann.time,
                    position: ann.type === 'swing_high' ? 'aboveBar' : 'belowBar',
                    color: ann.type === 'swing_high' ? '#f59e0b' : '#3b82f6',
                    shape: ann.type === 'swing_high' ? 'arrowDown' : 'arrowUp',
                    text: ann.text || '',
                });
            }
        });

        if (markers.length > 0) {
            // Sort markers by time
            markers.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
            candlestickSeries.setMarkers(markers);
        }

        const handleResize = () => {
            if (chartContainerRef.current) {
                chart.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
        };
    }, [data, annotations]);

    return (
        <div className="w-full rounded-xl overflow-hidden shadow-lg border border-slate-700">
            <div ref={chartContainerRef} />
        </div>
    );
};
