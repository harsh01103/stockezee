CREATE TABLE IF NOT EXISTS signal_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL,
    type VARCHAR(50) NOT NULL, -- e.g., 'VCP', 'POCKET_PIVOT'
    direction VARCHAR(10) NOT NULL, -- 'BULLISH', 'BEARISH'
    confidence NUMERIC(5, 2) NOT NULL,
    price_at_signal NUMERIC(10, 2) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_signal_registry_symbol ON signal_registry(symbol);
CREATE INDEX IF NOT EXISTS idx_signal_registry_type ON signal_registry(type);
CREATE INDEX IF NOT EXISTS idx_signal_registry_created_at ON signal_registry(created_at);
