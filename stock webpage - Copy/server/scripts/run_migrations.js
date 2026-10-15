import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config({ path: path.resolve(__dirname, '../.env') });

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE;

if (!SUPABASE_URL || !SUPABASE_KEY) {
    console.error('Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE in server/.env');
    process.exit(1);
}

// Combined migration SQL
const migrationSQL = `
-- Security Master
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

-- Company Document Features
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

-- Grant permissions to service_role and authenticated
GRANT ALL ON security_master TO service_role;
GRANT ALL ON company_document_features TO service_role;
GRANT SELECT ON security_master TO authenticated;
GRANT SELECT ON company_document_features TO authenticated;
GRANT ALL ON security_master TO anon;
GRANT ALL ON company_document_features TO anon;
`;

async function runMigration() {
    console.log('=== Running Supabase Migrations ===\n');
    
    // Use the Supabase SQL API (available via the project's pg endpoint)
    // The /rest/v1/rpc endpoint won't work for DDL, so we use the /pg endpoint
    const projectRef = SUPABASE_URL.replace('https://', '').replace('.supabase.co', '');
    
    // Try the Supabase SQL API endpoint
    const sqlEndpoint = `${SUPABASE_URL}/rest/v1/rpc/`;
    
    // Since we can't execute raw DDL via PostgREST, let's output the SQL
    // and instruct the user to run it in the Supabase Dashboard
    
    console.log('The Supabase REST API does not support DDL (CREATE TABLE) operations.');
    console.log('Please run the following SQL in your Supabase Dashboard > SQL Editor:\n');
    console.log('─'.repeat(60));
    console.log(migrationSQL);
    console.log('─'.repeat(60));
    
    // Also save it to a file for easy copy-paste
    const outPath = path.resolve(__dirname, '../migrations/00_combined_migration.sql');
    fs.writeFileSync(outPath, migrationSQL);
    console.log(`\nSQL also saved to: ${outPath}`);
    console.log('\nAfter running the migration, execute: node server/scripts/clean_supabase.js');
}

runMigration().catch(console.error);
