import type { VercelRequest, VercelResponse } from "@vercel/node";
import { getUnderlyingQuote } from "./service";
import { findUnderlying } from "../options/catalog";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  try {
    const symbol = typeof req.query.symbol === "string" ? req.query.symbol : undefined;
    const quote = await getUnderlyingQuote(findUnderlying(symbol));
    res.status(200).json(quote);
  } catch {
    res.status(500).json({ error: "Failed to load underlying quote" });
  }
}
