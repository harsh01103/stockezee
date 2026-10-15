import { VercelRequest, VercelResponse } from "@vercel/node";
import Parser from 'rss-parser';
import fetch from "node-fetch";

const parser = new Parser();

let cachedNews: any[] = [];
let lastFetchTime = 0;

async function scrapeAlternativeData() {
    let altNews: any[] = [];
    try {
        const [isbRes, invRes] = await Promise.all([
            fetch('https://www.reddit.com/r/IndianStreetBets/hot.json?limit=15').then(r => r.json()),
            fetch('https://www.reddit.com/r/IndiaInvestments/hot.json?limit=15').then(r => r.json())
        ]);

        const parserReddit = (data: any) => {
            if (!data || !data.data || !data.data.children) return [];
            return data.data.children.map((c: any) => ({
                title: c.data.title,
                text: c.data.selftext || '',
                link: `https://reddit.com${c.data.permalink}`,
                source: `Reddit: r/${c.data.subreddit}`,
                pubDate: new Date(c.data.created_utc * 1000).toISOString()
            }));
        };

        altNews = [...parserReddit(isbRes), ...parserReddit(invRes)];
    } catch (e: any) { console.error("Reddit Scrape Failed:", e.message); }
    return altNews;
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
    try {
        const ONE_HOUR = 60 * 60 * 1000;
        const now = Date.now();

        if (cachedNews.length > 0 && (now - lastFetchTime < ONE_HOUR)) {
            return res.status(200).json({ news: cachedNews });
        }

        let newNews: any[] = [];

        const feedUrls = [
            'https://news.google.com/rss/search?q=Indian+Stock+Market+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en',
            'https://news.google.com/rss/search?q=NSE+BSE+Smallcap+Midcap+Breakout&hl=en-IN&gl=IN&ceid=IN:en'
        ];

        const allFeeds = await Promise.all(feedUrls.map(url => parser.parseURL(url).catch(() => ({ items: [] }))));
        let rawArticles: any[] = [];
        allFeeds.forEach(f => f.items.forEach(i => rawArticles.push(i)));

        const altNews = await scrapeAlternativeData();
        const combinedFeed = [...rawArticles, ...altNews];

        for (const item of combinedFeed) {
            const title = (item.title || '');
            const content = (item.text || item.contentSnippet || '');

            if (/NSE|BSE|STOCK|MARKET|NIFTY|SENSEX/i.test(title) || item.source?.includes('Reddit')) {
                newNews.push({
                    title: item.title,
                    link: item.link,
                    pubDate: item.pubDate || new Date().toISOString(),
                    source: item.source || 'Institutional Scraper',
                    contentSnippet: content.substring(0, 150) + '...',
                    isVerified: true
                });
            }
        }

        cachedNews = newNews.length > 0 ? newNews.slice(0, 40) : [];
        lastFetchTime = now;

        res.status(200).json({ news: cachedNews });

    } catch (error) {
        console.error("News Scrape Error:", error);
        res.status(500).json({ error: "Failed to fetch global news." });
    }
}
