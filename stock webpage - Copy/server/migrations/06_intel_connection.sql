-- =============================================
-- Migration: Intel UI Connection & Retrieval
-- Adds tracking columns for UI extraction and retrieval ranking
-- Run this in Supabase Dashboard > SQL Editor
-- =============================================

-- Add retrieval_score to company_documents
ALTER TABLE company_documents 
ADD COLUMN IF NOT EXISTS retrieval_score NUMERIC(10, 2) DEFAULT 0;

-- Add tracking columns to company_document_features
ALTER TABLE company_document_features
ADD COLUMN IF NOT EXISTS document_id UUID,
ADD COLUMN IF NOT EXISTS confidence VARCHAR(20),
ADD COLUMN IF NOT EXISTS tone VARCHAR(20),
ADD COLUMN IF NOT EXISTS risk JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS guidance TEXT,
ADD COLUMN IF NOT EXISTS evidence TEXT,
ADD COLUMN IF NOT EXISTS retrieval_score NUMERIC(10, 2) DEFAULT 0;

-- Add foreign key constraint safely
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_features_document'
    ) THEN
        ALTER TABLE company_document_features 
        ADD CONSTRAINT fk_features_document FOREIGN KEY (document_id) REFERENCES company_documents(id) ON DELETE CASCADE;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_company_doc_features_document_id
ON company_document_features(document_id)
WHERE document_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_company_docs_retrieval_score
ON company_documents(retrieval_score DESC);

GRANT ALL ON company_documents TO service_role;
GRANT SELECT ON company_documents TO authenticated;
GRANT SELECT ON company_documents TO anon;

ALTER TABLE company_documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow public read on company_documents" ON company_documents;
DROP POLICY IF EXISTS "Allow service_role full access on company_documents" ON company_documents;

CREATE POLICY "Allow public read on company_documents" ON company_documents FOR SELECT USING (true);
CREATE POLICY "Allow service_role full access on company_documents" ON company_documents FOR ALL USING (true) WITH CHECK (true);
