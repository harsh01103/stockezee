import YahooFinance from 'yahoo-finance2';
import crypto from 'crypto';

const yahooFinance = new YahooFinance();

/**
 * Mocks fetching official exchange filings (e.g. from NSE/BSE corporate announcements)
 */
async function fetchOfficialFilings(symbol, exchange) {
    // For validation: Create a mock official filing for SBIN and WIPRO to test the ranking engine.
    if (symbol === 'SBIN') {
        const title = 'Outcome of Board Meeting - Financial Results';
        const url = 'https://www.bseindia.com/xml-data/corpfiling/SBIN_Results.pdf';
        return [{
            symbol,
            exchange,
            title,
            url,
            type: 'ANNOUNCEMENT',
            origin_type: 'FILING',
            source_name: 'BSE Corporate Announcements',
            is_primary_source: true,
            content_quality: 95,
            published_at: new Date().toISOString(),
            hash: crypto.createHash('sha256').update(symbol + url + title).digest('hex')
        }];
    }
    
    if (symbol === 'WIPRO') {
        const title = 'Press Release - Q3 Earnings';
        const url = 'https://www.nseindia.com/corporate/WIPRO_PR.pdf';
        return [{
            symbol,
            exchange,
            title,
            url,
            type: 'ANNOUNCEMENT',
            origin_type: 'FILING',
            source_name: 'NSE Corporate Announcements',
            is_primary_source: true,
            content_quality: 95,
            published_at: new Date().toISOString(),
            hash: crypto.createHash('sha256').update(symbol + url + title).digest('hex')
        }];
    }

    return [];
}

/**
 * Fetches recent news and announcements from Yahoo Finance for a given symbol.
 * This acts as the source for 'real' corporate documents.
 */
export async function fetchExchangeDocuments(symbol, exchange) {
    try {
        // Fetch Official Filings First
        const filings = await fetchOfficialFilings(symbol, exchange);

        // Search by plain symbol for better news relevance
        const newsResult = await yahooFinance.search(symbol, { newsCount: 5 });
        
        let mappedNews = [];
        
        if (newsResult && newsResult.news && newsResult.news.length > 0) {
            mappedNews = newsResult.news.map(article => {
                const url = article.link || article.url || '';
                const title = article.title || '';
                const sourceName = article.publisher || 'Yahoo Finance';
                
                const hash = crypto.createHash('sha256').update(symbol + url + title).digest('hex');
                
                // Base quality for generic NEWS is 40 (Will be rejected unless boosted)
                let quality = 40;
                if (title.toUpperCase().includes(symbol)) {
                    quality += 20; // High relevance boost (+20 -> 60, passes threshold)
                }
                if (article.summary && article.summary.length > 100) {
                    quality += 5; // Slight boost
                }

                return {
                    symbol,
                    exchange,
                    title,
                    url,
                    type: 'ANNOUNCEMENT',
                    origin_type: 'NEWS',
                    source_name: sourceName,
                    is_primary_source: false,
                    content_quality: quality,
                    published_at: article.providerPublishTime 
                        ? new Date(article.providerPublishTime).toISOString() 
                        : new Date().toISOString(),
                    hash
                };
            });
        }

        // Reject: quality < 50
        const validNews = mappedNews.filter(doc => doc.content_quality >= 50);

        // Combine filings and news
        return [...filings, ...validNews];
    } catch (e) {
        console.error(`[Fetchers] Error fetching exchange documents for ${symbol}: ${e.message}`);
        return [];
    }
}
