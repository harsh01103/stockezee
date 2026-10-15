CREATE TABLE IF NOT EXISTS security_master (
    instrument_id VARCHAR(50) PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    instrument_type VARCHAR(50) NOT NULL,
    series VARCHAR(20),
    isin VARCHAR(50),
    sector VARCHAR(100),
    industry VARCHAR(100),
    listing_status VARCHAR(50) DEFAULT 'ACTIVE',
    is_etf BOOLEAN DEFAULT FALSE,
    is_equity BOOLEAN DEFAULT FALSE,
    search_enabled BOOLEAN DEFAULT TRUE,
    paper_trade_enabled BOOLEAN DEFAULT TRUE,
    doc_enabled BOOLEAN DEFAULT TRUE,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_security_master_symbol_exch ON security_master(symbol, exchange);
CREATE INDEX IF NOT EXISTS idx_security_master_search ON security_master(search_enabled, is_equity, is_etf);
