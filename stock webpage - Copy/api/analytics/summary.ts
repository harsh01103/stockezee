import type { VercelRequest, VercelResponse } from "@vercel/node";
import { getInstruments } from "../utils";
import { buildAnalytics, getOptionChain } from "../../server/optionsService.js";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  try {
    const instruments = await getInstruments();
    const symbol = typeof req.query.symbol === "string" ? req.query.symbol : "NIFTY";
    const expiry = typeof req.query.expiry === "string" ? req.query.expiry : "";
    const chain = await getOptionChain(symbol, expiry, instruments, process.env.UPSTOX_ACCESS_TOKEN);
    res.status(200).json({
      generatedAt: chain.generatedAt,
      underlying: chain.underlying.symbol,
      expiry: chain.expiry,
      analytics: buildAnalytics(chain.rows),
    });
  } catch (error: any) {
    res.status(error?.status || 500).json({ error: error?.message || "Failed to derive analytics" });
  }
}
