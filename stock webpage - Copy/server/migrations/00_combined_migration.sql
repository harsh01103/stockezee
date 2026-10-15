-- =============================================
-- COMBINED MIGRATION: Security Master + Documents
-- Run this in Supabase Dashboard > SQL Editor
-- =============================================

-- 1. Security Master Table
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

-- 2. Company Document Features Table
CREATE TABLE IF NOT EXISTS company_document_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    filing_date DATE NOT NULL,
    sentiment_score NUMERIC(5, 2) DEFAULT 0,
    risk_factors JSONB DEFAULT '[]'::jsonb,
    growth_catalysts JSONB DEFAULT '[]'::jsonb,
    capex_trend VARCHAR(20) DEFAULT 'NEUTRAL',
    management_tone VARCHAR(20) DEFAULT 'NEUTRAL',
    extracted_text TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_company_doc_symbol ON company_document_features(symbol);
CREATE INDEX IF NOT EXISTS idx_company_doc_type ON company_document_features(document_type);
CREATE INDEX IF NOT EXISTS idx_company_doc_date ON company_document_features(filing_date);

-- 3. Grant permissions
GRANT ALL ON security_master TO service_role;
GRANT ALL ON company_document_features TO service_role;
GRANT SELECT ON security_master TO authenticated;
GRANT SELECT ON company_document_features TO authenticated;
GRANT ALL ON security_master TO anon;
GRANT ALL ON company_document_features TO anon;

-- 4. Enable RLS (but allow service_role full access)
ALTER TABLE security_master ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_document_features ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read on security_master" ON security_master FOR SELECT USING (true);
CREATE POLICY "Allow service_role full access on security_master" ON security_master FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow public read on company_document_features" ON company_document_features FOR SELECT USING (true);
CREATE POLICY "Allow service_role full access on company_document_features" ON company_document_features FOR ALL USING (true) WITH CHECK (true);
