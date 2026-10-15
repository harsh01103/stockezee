import { supabase } from "@/lib/supabaseClient";
import type { PaperPosition, WatchlistItem } from "../types";

const WATCHLIST_KEY = "options.watchlist";
const POSITIONS_KEY = "options.paper-positions";

function readLocal<T>(key: string): T[] {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T[]) : [];
  } catch {
    return [];
  }
}

function writeLocal<T>(key: string, value: T[]) {
  localStorage.setItem(key, JSON.stringify(value));
}

async function tryCloudRead<T>(table: string, userId: string) {
  const { data, error } = await supabase.from(table).select("*").eq("user_id", userId).order("created_at", { ascending: false });
  if (error) {
    throw error;
  }
  return (data ?? []) as T[];
}

async function tryCloudReplace<T extends { createdAt: string }>(
  table: string,
  userId: string,
  items: T[]
) {
  const { error: deleteError } = await supabase.from(table).delete().eq("user_id", userId);
  if (deleteError) {
    throw deleteError;
  }

  if (items.length === 0) {
    return;
  }

  const payload = items.map((item) => ({
    ...item,
    user_id: userId,
    created_at: item.createdAt,
  }));

  const { error: insertError } = await supabase.from(table).insert(payload);
  if (insertError) {
    throw insertError;
  }
}

export const optionsPersistence = {
  async loadWatchlist(userId?: string | null) {
    const local = readLocal<WatchlistItem>(WATCHLIST_KEY);
    if (!userId) return local;

    try {
      const cloud = await tryCloudRead<WatchlistItem & { created_at?: string }>("watchlist", userId);
      return cloud.map((item) => ({
        ...item,
        createdAt: item.createdAt ?? item.created_at ?? new Date().toISOString(),
      }));
    } catch {
      return local;
    }
  },
  async saveWatchlist(items: WatchlistItem[], userId?: string | null) {
    writeLocal(WATCHLIST_KEY, items);
    if (!userId) return;

    try {
      await tryCloudReplace("watchlist", userId, items);
    } catch {
      return;
    }
  },
  async loadPaperPositions(userId?: string | null) {
    const local = readLocal<PaperPosition>(POSITIONS_KEY);
    if (!userId) return local;

    try {
      const cloud = await tryCloudRead<PaperPosition & { created_at?: string }>("paper_positions", userId);
      return cloud.map((item) => ({
        ...item,
        createdAt: item.createdAt ?? item.created_at ?? new Date().toISOString(),
      }));
    } catch {
      return local;
    }
  },
  async savePaperPositions(items: PaperPosition[], userId?: string | null) {
    writeLocal(POSITIONS_KEY, items);
    if (!userId) return;

    try {
      await tryCloudReplace("paper_positions", userId, items);
    } catch {
      return;
    }
  },
};
