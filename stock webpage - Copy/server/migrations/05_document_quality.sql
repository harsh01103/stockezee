-- =============================================
-- Migration: Company Intelligence Upgrade
-- Adds primary source and quality ranking columns
-- Run this in Supabase Dashboard > SQL Editor
-- =============================================

ALTER TABLE company_documents 
ADD COLUMN IF NOT EXISTS origin_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS source_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS is_primary_source BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS content_quality NUMERIC(5, 2) DEFAULT 0;

-- Optional: Update existing 'ANNOUNCEMENT' or null types to 'NEWS'
UPDATE company_documents SET origin_type = 'NEWS' WHERE origin_type IS NULL;
UPDATE company_documents SET is_primary_source = false WHERE is_primary_source IS NULL;

-- Ensure our hash constraint exists for the upsert logic if it was missing previously
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uk_company_documents_hash'
    ) THEN
        ALTER TABLE company_documents ADD CONSTRAINT uk_company_documents_hash UNIQUE (hash);
    END IF;
END $$;
