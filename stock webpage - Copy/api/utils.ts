import fetch from "node-fetch";
import csv from "csv-parser";
import { Readable } from "stream";
import zlib from "zlib";

export interface Instrument {
    instrument_key: string;
    exchange: string;
    symbol: string;
    name: string;
    exchanges?: string[];
    instrument_keys?: Record<string, string>;
}

let cachedInstruments: Instrument[] | null = null;
let isLoading = false;
let loadPromise: Promise<Instrument[]> | null = null;

export async function getInstruments(): Promise<Instrument[]> {
    if (cachedInstruments) return cachedInstruments;
    if (isLoading && loadPromise) return loadPromise;

    isLoading = true;
    loadPromise = (async () => {
        try {
            const exchanges = ['NSE', 'BSE'];
            let all: Instrument[] = [];
            for (const exch of exchanges) {
                const res = await fetch(`https://assets.upstox.com/market-quote/instruments/exchange/${exch}.csv.gz`);
                const arrayBuffer = await res.arrayBuffer();
                const buffer = Buffer.from(arrayBuffer);
                const results: Instrument[] = [];

                // Unzip the gzip buffer
                const unzipped = zlib.gunzipSync(buffer);
                const stream = Readable.from(unzipped);

                await new Promise<void>((resolve) => {
                    stream.pipe(csv()).on('data', (d: any) => {
                        if (d.instrument_type === 'EQUITY') {
                            results.push({
                                instrument_key: String(d.instrument_key),
                                exchange: String(d.exchange),
                                symbol: String(d.tradingsymbol),
                                name: String(d.name)
                            });
                        }
                    }).on('end', () => {
                        all = [...all, ...results];
                        resolve();
                    });
                });
            }
            cachedInstruments = all;
            console.log(`Loaded ${all.length} instruments from NSE/BSE.`);
            return all;
        } catch (e: any) {
            console.error("Error loading instruments:", e.message);
            return [];
        } finally {
            isLoading = false;
        }
    })();

    return loadPromise;
}
