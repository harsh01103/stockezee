CREATE TABLE IF NOT EXISTS shadow_leaderboard (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_name VARCHAR(50) NOT NULL, -- 'HUMAN_USER' or 'ALPHA_ENGINE'
    entity_type VARCHAR(20) NOT NULL,
    win_rate NUMERIC(5, 2) DEFAULT 0,
    total_pnl NUMERIC(15, 2) DEFAULT 0,
    sharpe_ratio NUMERIC(5, 2) DEFAULT 0,
    max_drawdown NUMERIC(5, 2) DEFAULT 0,
    trades_executed INTEGER DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_shadow_entity ON shadow_leaderboard(entity_name);

-- Insert defaults
INSERT INTO shadow_leaderboard (entity_name, entity_type, win_rate, total_pnl, sharpe_ratio, max_drawdown, trades_executed)
VALUES 
('Alpha Engine v5.0', 'MODEL', 62.5, 45200.00, 2.1, 4.5, 342),
('Human Benchmark', 'HUMAN', 48.2, 12500.00, 1.2, 8.5, 128)
ON CONFLICT (entity_name) DO NOTHING;
