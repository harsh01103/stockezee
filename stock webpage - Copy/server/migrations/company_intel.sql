CREATE TABLE IF NOT EXISTS company_document_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL,
    document_type VARCHAR(50) NOT NULL, -- 'ANNUAL_REPORT', 'QUARTERLY_EARNINGS', 'MANAGEMENT_COMMENTARY'
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
