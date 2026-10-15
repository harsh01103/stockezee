/**
 * Document-first intelligence pipeline.
 *
 * The database is a cache only. Runtime flow is:
 * symbol -> discover documents -> parse metadata -> extract features -> rank -> return -> cache.
 */

import { createClient } from '@supabase/supabase-js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
import axios from 'axios';
import { fetchExchangeDocuments } from './fetchers/exchangeFetcher.js';
import { fetchIRDocuments } from './fetchers/investorRelationsFetcher.js';
import { fetchPDFDocuments } from './fetchers/pdfFetcher.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config({ path: path.resolve(__dirname, '../../.env') });

import ws from 'ws';

const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE, {
    auth: { persistSession: false },
    realtime: { transport: ws }
});
const CACHE_TTL_MS = Number(process.env.DOC_INTEL_CACHE_TTL_MS || 6 * 60 * 60 * 1000);
const DEFAULT_EXCHANGE = 'NSE_EQ';

const SOURCE_PRIORITY = {
    FILING: 1,
    ANNOUNCEMENT: 1,
    ANNUAL_REPORT: 2,
    QUARTERLY_REPORT: 3,
    PRESENTATION: 4,
    TRANSCRIPT: 5,
    NEWS: 6
};

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
const asDate = (value) => {
    const date = value ? new Date(value) : new Date();
    return Number.isNaN(date.getTime()) ? new Date() : date;
};

function missingColumnName(error) {
    const match = error?.message?.match(/'([^']+)' column/);
    return match?.[1];
}

function confidenceFromScore(score) {
    if (score >= 25) return 'HIGH';
    if (score >= 15) return 'MEDIUM';
    return 'LOW';
}

function getDocumentFacts(item) {
    const document = item.document || item.company_documents || item;
    const feature = item.feature || item;
    const metadata = feature.metadata || document.metadata || {};

    return {
        documentId: feature.document_id || document.id,
        originType: document.origin_type || metadata.origin_type || feature.document_type || document.type || 'NEWS',
        publishedAt: document.published_at || feature.filing_date || metadata.document_date,
        isPrimarySource: Boolean(document.is_primary_source ?? metadata.is_primary_source),
        contentQuality: Number(document.content_quality ?? metadata.content_quality ?? 50),
        duplicateKey: document.hash || document.url || document.title || feature.evidence || feature.document_type || 'UNKNOWN'
    };
}

function computeRetrievalScore(item, duplicateIndex = 0) {
    const facts = getDocumentFacts(item);
    const base = 10;
    const primaryMultiplier = facts.isPrimarySource ? 2.0 : 1.0;
    const ageDays = Math.max(0, (Date.now() - asDate(facts.publishedAt).getTime()) / (1000 * 60 * 60 * 24));
    const freshness = clamp(1.5 - (ageDays / 180), 0.5, 1.5);
    const quality = clamp(facts.contentQuality / 50, 0.5, 2.0);
    const duplicatePenalty = Math.max(0.25, 1.0 - (duplicateIndex * 0.2));

    return Number((base * primaryMultiplier * freshness * quality * duplicatePenalty).toFixed(2));
}

function parseDocument(doc) {
    const title = doc.title || '';
    const url = doc.url || '';
    const text = `${title} ${doc.source_name || ''} ${doc.origin_type || ''} ${doc.type || ''}`.toLowerCase();

    return {
        text,
        evidence: url || title,
        parsedSummary: `Verified document metadata: ${title || url}`,
        hasGuidance: /guidance|outlook|forecast|projection|estimate/.test(text),
        hasCapex: /capex|capital expenditure|capacity|expansion|investment/.test(text),
        isFinancialResult: /result|earnings|quarter|financial/.test(text)
    };
}

// Note: This function now should be async, so we'll rename it to extractFeaturesAsync
async function extractFeaturesAsync(doc) {
    const parsed = parseDocument(doc);
    const originType = doc.origin_type || doc.type || 'NEWS';
    const isPrimary = Boolean(doc.is_primary_source);
    const quality = Number(doc.content_quality || 50);

    let facts = [];

    // Call Python Microservice for PDF extraction if it's a PDF
    if (doc.url && doc.url.endsWith('.pdf')) {
        try {
            const { data } = await axios.post('http://127.0.0.1:8000/extract', {
                url: doc.url,
                symbol: doc.symbol
            }, { timeout: 20000 });
            
            if (data && data.facts) {
                facts = data.facts.map(f => ({
                    ...f,
                    confidence: f.confidence * (quality / 100)
                }));
            }
        } catch (e) {
            console.warn(`[DocIntel] Python microservice failed for ${doc.symbol}: ${e.message}`);
        }
    }

    // Fallback or non-PDF logic
    if (facts.length === 0) {
        if (parsed.hasGuidance) facts.push({ metric: 'GUIDANCE_UPDATED', value: 'YES', period: 'CURRENT', confidence: 0.5 });
        if (parsed.hasCapex) facts.push({ metric: 'CAPEX_ANNOUNCED', value: 'YES', period: 'FORWARD', confidence: 0.5 });
        if (parsed.isFinancialResult) facts.push({ metric: 'FINANCIAL_RESULTS_FILED', value: 'YES', period: 'RECENT', confidence: 0.8 });
    }

    return {
        symbol: doc.symbol,
        document_type: originType,
        filing_date: asDate(doc.published_at).toISOString().split('T')[0],
        extracted_facts: facts,
        evidence: parsed.evidence,
        metadata: {
            source_title: doc.title,
            source_url: doc.url,
            source_name: doc.source_name,
            origin_type: originType,
            is_primary_source: isPrimary,
            content_quality: quality,
            document_date: asDate(doc.published_at).toISOString()
        }
    };
}

function sortBySourcePriority(docs) {
    return [...docs].sort((a, b) => {
        const priorityA = SOURCE_PRIORITY[a.origin_type] || SOURCE_PRIORITY[a.type] || 99;
        const priorityB = SOURCE_PRIORITY[b.origin_type] || SOURCE_PRIORITY[b.type] || 99;
        if (priorityA !== priorityB) return priorityA - priorityB;
        return Number(b.content_quality || 0) - Number(a.content_quality || 0);
    });
}

async function getCachedIntel(symbol) {
    try {
        let { data, error } = await supabase
            .from('company_document_features')
            .select(`
                *,
                company_documents!fk_features_document (
                    id,
                    symbol,
                    exchange,
                    title,
                    url,
                    type,
                    origin_type,
                    source_name,
                    published_at,
                    is_primary_source,
                    content_quality,
                    retrieval_score,
                    hash
                )
            `)
            .eq('symbol', symbol)
            .order('retrieval_score', { ascending: false });

        if (error && error.message?.includes('Could not find a relationship')) {
            const fallback = await supabase
                .from('company_document_features')
                .select('*')
                .eq('symbol', symbol);

            if (fallback.error) return [];

            const documentIds = [...new Set((fallback.data || []).map(row => row.document_id).filter(Boolean))];
            const documentQuery = documentIds.length > 0
                ? supabase.from('company_documents').select('*').in('id', documentIds)
                : supabase.from('company_documents').select('*').eq('symbol', symbol);
            const { data: documents } = await documentQuery;
            const documentsById = new Map((documents || []).map(doc => [doc.id, doc]));

            data = (fallback.data || []).map(row => ({
                ...row,
                company_documents: documentsById.get(row.document_id) || null
            }));
            error = null;
        }

        if (error || !data?.length) return [];

        const freshRows = data.filter(row => {
            const createdAt = row.created_at ? new Date(row.created_at).getTime() : 0;
            return createdAt > 0 && Date.now() - createdAt < CACHE_TTL_MS;
        });

        return rankFeatureRows(freshRows);
    } catch (error) {
        console.warn(`[DocIntel] Cache read skipped for ${symbol}: ${error.message}`);
        return [];
    }
}

async function discoverDocuments(symbol, exchange = DEFAULT_EXCHANGE) {
    const [exchangeDocs, irDocs, pdfDocs] = await Promise.all([
        fetchExchangeDocuments(symbol, exchange),
        fetchIRDocuments(symbol, exchange),
        fetchPDFDocuments(symbol, exchange)
    ]);

    const byHash = new Map();
    for (const doc of sortBySourcePriority([...exchangeDocs, ...irDocs, ...pdfDocs])) {
        const key = doc.hash || `${doc.symbol}:${doc.url || doc.title}`;
        if (!byHash.has(key)) byHash.set(key, doc);
    }

    return [...byHash.values()];
}

function rankDocumentAnalyses(items) {
    const duplicateCounts = {};
    return items
        .map(item => {
            const facts = getDocumentFacts(item);
            const duplicateIndex = duplicateCounts[facts.duplicateKey] || 0;
            duplicateCounts[facts.duplicateKey] = duplicateIndex + 1;
            const retrievalScore = computeRetrievalScore(item, duplicateIndex);

            return {
                ...item.feature,
                document: item.document,
                document_id: item.document.id,
                confidence: confidenceFromScore(retrievalScore),
                retrieval_score: retrievalScore,
                _computedRankScore: retrievalScore
            };
        })
        .sort((a, b) => b._computedRankScore - a._computedRankScore);
}

function rankFeatureRows(rows) {
    const duplicateCounts = {};
    return rows
        .map(row => {
            const document = Array.isArray(row.company_documents)
                ? row.company_documents[0]
                : row.company_documents;
            const item = { feature: row, document };
            const facts = getDocumentFacts(item);
            const duplicateIndex = duplicateCounts[facts.duplicateKey] || 0;
            duplicateCounts[facts.duplicateKey] = duplicateIndex + 1;
            const retrievalScore = computeRetrievalScore(item, duplicateIndex);

            return {
                ...row,
                company_documents: document,
                confidence: row.confidence || confidenceFromScore(retrievalScore),
                retrieval_score: retrievalScore,
                _computedRankScore: retrievalScore
            };
        })
        .sort((a, b) => b._computedRankScore - a._computedRankScore);
}

async function writeFeatureRow(analysis, featureId = null) {
    const payload = { ...analysis };

    for (let attempt = 0; attempt < 10; attempt++) {
        const query = featureId
            ? supabase.from('company_document_features').update(payload).eq('id', featureId)
            : supabase.from('company_document_features').insert([payload]);

        const { data, error } = await query.select().single();
        if (!error) return { data, error: null };

        const missingColumn = missingColumnName(error);
        if (!missingColumn || !(missingColumn in payload)) {
            return { data: null, error };
        }

        delete payload[missingColumn];
    }

    return { data: null, error: new Error('Failed to persist features after removing unavailable columns.') };
}

async function cacheRankedResults(rankedItems) {
    const cached = [];

    for (const item of rankedItems) {
        try {
            const documentPayload = {
                ...item.document,
                retrieval_score: item.retrieval_score
            };
            
            // Remove schema-incompatible fields
            delete documentPayload.content_quality;

            const { data: documentRow, error: documentError } = await supabase
                .from('company_documents')
                .upsert(documentPayload, { onConflict: 'hash' })
                .select('id')
                .single();

            if (documentError) throw documentError;

            // Write structured facts to extracted_facts table instead of JSONB
            if (item.extracted_facts && item.extracted_facts.length > 0) {
                const factsPayload = item.extracted_facts.map(fact => ({
                    symbol: item.symbol,
                    document_id: documentRow.id,
                    metric: fact.metric,
                    value: fact.value,
                    period: fact.period,
                    evidence_date: item.filing_date,
                    source_url: item.evidence,
                    confidence: fact.confidence * (item.retrieval_score / 100) // Adjusted confidence
                }));

                const { error: factsError } = await supabase
                    .from('extracted_facts')
                    .upsert(factsPayload, { onConflict: 'document_id,metric' });

                if (factsError) throw factsError;
            }

            cached.push({
                ...item,
                id: featureRow?.id || item.id,
                document_id: documentRow.id,
                company_documents: {
                    ...item.document,
                    id: documentRow.id,
                    retrieval_score: item.retrieval_score
                }
            });
        } catch (error) {
            console.warn(`[DocIntel] Cache write skipped for ${item.symbol}: ${error.message}`);
            cached.push(item);
        }
    }

    return cached;
}

export const docIntelPipeline = {
    async processFiling(documentId) {
        const { data: doc, error } = await supabase
            .from('company_documents')
            .select('*')
            .eq('id', documentId)
            .maybeSingle();

        if (error || !doc) {
            throw new Error(`Document ${documentId} not found or db error.`);
        }

        const feature = await extractFeaturesAsync(doc);
        const ranked = rankDocumentAnalyses([{ document: doc, feature }]);
        const [cached] = await cacheRankedResults(ranked);
        return cached;
    },

    async fetchCompanyIntel(symbol, options = {}) {
        const normalizedSymbol = String(symbol || '').trim().toUpperCase();
        const exchange = options.exchange || DEFAULT_EXCHANGE;

        if (!normalizedSymbol) {
            throw new Error('Symbol is required.');
        }

        const stages = ['Searching', 'Fetching documents', 'Parsing', 'Ranking', 'Done'];
        const cached = options.forceRefresh ? [] : await getCachedIntel(normalizedSymbol);
        if (cached.length > 0) {
            return {
                symbol: normalizedSymbol,
                cache: 'hit',
                stages,
                documents_found: cached.length,
                results: cached
            };
        }

        const documents = await discoverDocuments(normalizedSymbol, exchange);
        if (documents.length === 0) {
            return {
                symbol: normalizedSymbol,
                cache: 'miss',
                stages,
                documents_found: 0,
                fetch_failed: true,
                results: []
            };
        }

        const analyses = await Promise.all(documents.map(async document => ({
            document,
            feature: await extractFeaturesAsync(document)
        })));
        const ranked = rankDocumentAnalyses(analyses);
        const cachedResults = await cacheRankedResults(ranked);

        return {
            symbol: normalizedSymbol,
            cache: 'miss',
            stages,
            documents_found: documents.length,
            results: cachedResults
        };
    },

    async getCompanyIntel(symbol, options = {}) {
        const response = await this.fetchCompanyIntel(symbol, options);
        return response.results;
    }
};
