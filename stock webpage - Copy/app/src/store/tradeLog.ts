// Shared trade log store — uses Supabase for secure per-user storage
// Trades older than 30 days are filtered out on query (not deleted, just hidden)

import { supabase } from '../lib/supabaseClient';

export interface TradeEntry {
    id: string;
    user_id: string;
    symbol: string;
    name: string;
    type: 'BUY' | 'SELL';
    qty: number;
    price: number;
    total: number;
    pnl?: number | null;
    category: 'stock' | 'commodity';
    created_at: string;
}

/** Fetch trades from the last 30 days for the current user */
export async function getTrades(): Promise<TradeEntry[]> {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return [];

    const cutoff = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();

    const { data, error } = await supabase
        .from('trades')
        .select('*')
        .eq('user_id', user.id)
        .gte('created_at', cutoff)
        .order('created_at', { ascending: false });

    if (error) {
        console.error('Error fetching trades:', error.message);
        return [];
    }

    return data || [];
}

/** Add a new trade entry for the current user */
export async function addTrade(trade: {
    symbol: string;
    name: string;
    type: 'BUY' | 'SELL';
    qty: number;
    price: number;
    total: number;
    pnl?: number;
    category: 'stock' | 'commodity';
}): Promise<TradeEntry | null> {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) {
        console.warn('Cannot log trade: user not authenticated');
        return null;
    }

    const { data, error } = await supabase
        .from('trades')
        .insert({
            user_id: user.id,
            symbol: trade.symbol,
            name: trade.name,
            type: trade.type,
            qty: trade.qty,
            price: trade.price,
            total: trade.total,
            pnl: trade.pnl ?? null,
            category: trade.category,
        })
        .select()
        .single();

    if (error) {
        console.error('Error logging trade:', error.message);
        return null;
    }

    return data;
}

/** Get daily P&L summary for calendar (last 30 days) */
export async function getDailyPnL(): Promise<Record<string, { pnl: number; trades: number }>> {
    const trades = await getTrades();
    const daily: Record<string, { pnl: number; trades: number }> = {};

    for (const t of trades) {
        const dateKey = new Date(t.created_at).toISOString().split('T')[0];
        if (!daily[dateKey]) {
            daily[dateKey] = { pnl: 0, trades: 0 };
        }
        daily[dateKey].trades += 1;
        if (t.pnl != null) {
            daily[dateKey].pnl += Number(t.pnl);
        }
    }

    return daily;
}

/** Clear all trades for the current user */
export async function clearTrades(): Promise<void> {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    const { error } = await supabase
        .from('trades')
        .delete()
        .eq('user_id', user.id);

    if (error) {
        console.error('Error clearing trades:', error.message);
    }
}
