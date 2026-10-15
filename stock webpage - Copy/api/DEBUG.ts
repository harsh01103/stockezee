import { VercelRequest, VercelResponse } from "@vercel/node";
import yf from "yahoo-finance2";

export default async function handler(req: VercelRequest, res: VercelResponse) {
    try {
        const typeOfDefault = typeof yf;
        const keys = Object.keys(yf || {});

        let hasChart = typeof (yf as any).chart === 'function';
        let defaultHasChart = typeof (yf as any).default?.chart === 'function';

        return res.status(200).json({
            typeOfYf: typeOfDefault,
            keys,
            hasChart,
            defaultHasChart,
            isYfConstructor: typeof yf === 'function',
            YfToString: String(yf).substring(0, 100),
            defaultToString: String((yf as any).default).substring(0, 100),
            ts: Date.now()
        });
    } catch (e: any) {
        return res.status(500).json({ error: e.message, stack: e.stack });
    }
}
