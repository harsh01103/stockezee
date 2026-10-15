import { useEffect, useRef } from 'react';
import { createChart, ColorType } from 'lightweight-charts';

interface OHLCV {
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

interface Annotation {
    type: string;
    price: number;
    text?: string;
    time?: string;
}

interface TradePlan {
    entry_trigger?: number;
    stop_loss?: number;
    target_1?: number;
}

interface LightweightChartProps {
    data: OHLCV[];
    annotations?: Annotation[];
    plan?: TradePlan | null;
}

export function LightweightChart({ data, annotations, plan }: LightweightChartProps) {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<any>(null);

    useEffect(() => {
        if (!chartContainerRef.current || !data || data.length === 0) return;

        // Clean up previous chart
        if (chartRef.current) {
            chartRef.current.remove();
        }

        const handleResize = () => {
            if (chartContainerRef.current && chartRef.current) {
                chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: '#050505' },
                textColor: '#94a3b8',
            },
            grid: {
                vertLines: { color: 'rgba(30, 41, 59, 0.5)' },
                horzLines: { color: 'rgba(30, 41, 59, 0.5)' },
            },
            width: chartContainerRef.current.clientWidth,
            height: 500,
            crosshair: {
                mode: 0,
            },
            timeScale: {
                borderColor: 'rgba(30, 41, 59, 1)',
            },
        });
        
        chartRef.current = chart;

        const candlestickSeries = chart.addCandlestickSeries({
            upColor: '#10b981',
            downColor: '#ef4444',
            borderVisible: false,
            wickUpColor: '#10b981',
            wickDownColor: '#ef4444',
        });

        // Map data
        const chartData = data.map(d => ({
            time: d.date,
            open: d.open,
            high: d.high,
            low: d.low,
            close: d.close,
        }));

        candlestickSeries.setData(chartData);

        // Add volume series
        const volumeSeries = chart.addHistogramSeries({
            color: '#26a69a',
            priceFormat: {
                type: 'volume',
            },
            priceScaleId: '', // set as an overlay
            scaleMargins: {
                top: 0.8, // highest point of the series will be at 80% of the chart height
                bottom: 0,
            },
        });

        const volumeData = data.map(d => ({
            time: d.date,
            value: d.volume,
            color: d.close >= d.open ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)',
        }));
        
        volumeSeries.setData(volumeData);

        // Add trade plan lines if available
        if (plan) {
            if (plan.entry_trigger) {
                candlestickSeries.createPriceLine({
                    price: plan.entry_trigger,
                    color: '#10b981', // Emerald
                    lineWidth: 2,
                    lineStyle: 2, // Dashed
                    axisLabelVisible: true,
                    title: 'Entry',
                });
            }
            if (plan.stop_loss) {
                candlestickSeries.createPriceLine({
                    price: plan.stop_loss,
                    color: '#ef4444', // Red
                    lineWidth: 2,
                    lineStyle: 2,
                    axisLabelVisible: true,
                    title: 'Stop',
                });
            }
            if (plan.target_1) {
                candlestickSeries.createPriceLine({
                    price: plan.target_1,
                    color: '#06b6d4', // Cyan
                    lineWidth: 2,
                    lineStyle: 2,
                    axisLabelVisible: true,
                    title: 'Target 1',
                });
            }
        }

        // Add support/resistance annotations
        if (annotations) {
            let sCount = 1;
            let rCount = 1;
            annotations.forEach(a => {
                if (a.type === 'support') {
                    candlestickSeries.createPriceLine({
                        price: a.price,
                        color: 'rgba(59, 130, 246, 0.5)', // Blue semi-transparent
                        lineWidth: 1,
                        lineStyle: 1, // Dotted
                        axisLabelVisible: false,
                        title: a.text || `S${sCount++}`,
                    });
                } else if (a.type === 'resistance') {
                    candlestickSeries.createPriceLine({
                        price: a.price,
                        color: 'rgba(245, 158, 11, 0.5)', // Amber semi-transparent
                        lineWidth: 1,
                        lineStyle: 1,
                        axisLabelVisible: false,
                        title: a.text || `R${rCount++}`,
                    });
                }
            });
        }

        chart.timeScale().fitContent();

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            if (chartRef.current) {
                chartRef.current.remove();
            }
        };
    }, [data, annotations, plan]);

    return (
        <div className="rounded-xl overflow-hidden border border-slate-700/50 relative" style={{ height: '500px' }}>
            <div ref={chartContainerRef} style={{ width: '100%', height: '100%' }} />
        </div>
    );
}
