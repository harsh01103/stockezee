-- Run this in your Supabase Dashboard > SQL Editor
-- Creates the trades table with Row Level Security

CREATE TABLE IF NOT EXISTS trades (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('BUY', 'SELL')),
    qty INTEGER NOT NULL,
    price NUMERIC(12, 2) NOT NULL,
    total NUMERIC(14, 2) NOT NULL,
    pnl NUMERIC(14, 2),
    category TEXT NOT NULL CHECK (category IN ('stock', 'commodity')),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Enable Row Level Security
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only INSERT their own trades
CREATE POLICY "Users can insert own trades"
    ON trades FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Policy: Users can only SELECT their own trades
CREATE POLICY "Users can read own trades"
    ON trades FOR SELECT
    USING (auth.uid() = user_id);

-- Policy: Users can only DELETE their own trades
CREATE POLICY "Users can delete own trades"
    ON trades FOR DELETE
    USING (auth.uid() = user_id);

-- Index for fast queries by user + date
CREATE INDEX idx_trades_user_date ON trades (user_id, created_at DESC);
