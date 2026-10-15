CREATE TABLE IF NOT EXISTS company_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    title VARCHAR(255) NOT NULL,
    url VARCHAR(500),
    type VARCHAR(50) NOT NULL, -- 'ANNUAL_REPORT', 'QUARTERLY_REPORT', 'ANNOUNCEMENT', 'PRESENTATION', 'TRANSCRIPT'
    published_at TIMESTAMP WITH TIME ZONE,
    hash VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_security FOREIGN KEY (symbol, exchange) REFERENCES security_master(symbol, exchange) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_company_docs_symbol ON company_documents(symbol, exchange);
CREATE INDEX IF NOT EXISTS idx_company_docs_type ON company_documents(type);
