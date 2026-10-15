import { VercelRequest, VercelResponse } from "@vercel/node";
import { getInstruments, Instrument } from "./utils";

export default async function handler(req: VercelRequest, res: VercelResponse) {
    const { q } = req.query;
    if (!q || typeof q !== "string" || q.length < 2) {
        return res.status(200).json([]);
    }

    const query = q.toLowerCase();
    const instruments = await getInstruments();

    const matches = instruments.filter(
        (i) =>
            i.symbol.toLowerCase().includes(query) ||
            i.name.toLowerCase().includes(query)
    );

    const grouped = new Map<string, Instrument>();
    for (const item of matches) {
        if (!grouped.has(item.symbol)) {
            grouped.set(item.symbol, {
                ...item,
                exchanges: [item.exchange],
                instrument_keys: { [item.exchange]: item.instrument_key }
            });
        } else {
            const existing = grouped.get(item.symbol)!;
            if (!existing.exchanges!.includes(item.exchange)) {
                existing.exchanges!.push(item.exchange);
                existing.instrument_keys![item.exchange] = item.instrument_key;
            }
        }
    }

    res.status(200).json(Array.from(grouped.values()).slice(0, 15));
}
