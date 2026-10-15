CREATE TABLE IF NOT EXISTS trade_replay_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    signal_id UUID, -- References signal_registry if this replay is tied to a specific signal
    initial_price NUMERIC(10, 2),
    final_price NUMERIC(10, 2),
    market_regime VARCHAR(50),
    data_points JSONB NOT NULL DEFAULT '[]'::jsonb, -- Array of 1m candles and option chain snapshots
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trade_replay_symbol ON trade_replay_sessions(symbol);
CREATE INDEX IF NOT EXISTS idx_trade_replay_dates ON trade_replay_sessions(start_time, end_time);
