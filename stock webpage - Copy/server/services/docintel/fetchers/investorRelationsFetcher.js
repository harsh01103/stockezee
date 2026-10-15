import crypto from 'crypto';

async function fetchAnnualReports(symbol, exchange) {
    if (symbol === 'RELIANCE') {
        const title = 'Annual Report 2025-26';
        const url = 'https://www.ril.com/investors/annual-report.pdf';
        return [{
            symbol,
            exchange,
            title,
            url,
            type: 'ANNUAL_REPORT',
            origin_type: 'ANNUAL_REPORT',
            source_name: 'Reliance Investor Relations',
            is_primary_source: true,
            content_quality: 90, 
            published_at: new Date().toISOString(),
            hash: crypto.createHash('sha256').update(symbol + url + title).digest('hex')
        }];
    }
    return [];
}

async function fetchQuarterlyReports(symbol, exchange) {
    if (symbol === 'WIPRO') {
        const title = 'Q3 Earnings Transcript';
        const url = 'https://www.wipro.com/investors/q3-transcript.pdf';
        return [{
            symbol,
            exchange,
            title,
            url,
            type: 'TRANSCRIPT',
            origin_type: 'TRANSCRIPT',
            source_name: 'Wipro Investor Relations',
            is_primary_source: true,
            content_quality: 75,
            published_at: new Date().toISOString(),
            hash: crypto.createHash('sha256').update(symbol + url + title).digest('hex')
        }];
    }
    return [];
}

async function fetchInvestorPresentations(symbol, exchange) {
    if (symbol === 'SBIN') {
        const title = 'Investor Presentation - Fiscal Year 2026';
        const url = 'https://sbi.co.in/investors/presentation.pdf';
        return [{
            symbol,
            exchange,
            title,
            url,
            type: 'PRESENTATION',
            origin_type: 'PRESENTATION',
            source_name: 'SBI Investor Relations',
            is_primary_source: true,
            content_quality: 80,
            published_at: new Date().toISOString(),
            hash: crypto.createHash('sha256').update(symbol + url + title).digest('hex')
        }];
    }
    return [];
}

/**
 * Main fetcher for IR documents
 */
export async function fetchIRDocuments(symbol, exchange) {
    const annuals = await fetchAnnualReports(symbol, exchange);
    const quarterlies = await fetchQuarterlyReports(symbol, exchange);
    const presentations = await fetchInvestorPresentations(symbol, exchange);
    
    const allDocs = [...annuals, ...quarterlies, ...presentations];
    
    // Filter out < 50 quality, though all mock sources are high quality
    return allDocs.filter(doc => doc.content_quality >= 50);
}
