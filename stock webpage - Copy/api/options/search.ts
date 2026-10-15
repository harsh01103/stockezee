import type { VercelRequest, VercelResponse } from "@vercel/node";
import { getInstruments } from "../utils";
import { searchOptionUnderlyings } from "../../server/optionsService.js";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  try {
    const instruments = await getInstruments();
    const query = typeof req.query.q === "string" ? req.query.q : "";
    res.status(200).json(searchOptionUnderlyings(query, instruments));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to search option underlyings";
    res.status(500).json({ error: message });
  }
}
