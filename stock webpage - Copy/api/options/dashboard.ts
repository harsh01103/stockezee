import type { VercelRequest, VercelResponse } from "@vercel/node";
import { getInstruments } from "../utils";
import { getOptionsDashboard } from "../../server/optionsService.js";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  try {
    const instruments = await getInstruments();
    const symbol = typeof req.query.symbol === "string" ? req.query.symbol : "NIFTY";
    const data = await getOptionsDashboard(symbol, instruments, process.env.UPSTOX_ACCESS_TOKEN);
    res.status(200).json(data);
  } catch (error: any) {
    res.status(error?.status || 500).json({ error: error?.message || "Failed to load options dashboard" });
  }
}
