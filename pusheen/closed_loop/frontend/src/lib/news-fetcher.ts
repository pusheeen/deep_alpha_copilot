/**
 * News fetching service — Google News RSS, custom RSS feeds.
 * Runs server-side in Next.js API routes.
 */
import { cacheGet, cacheSet, makeCacheKey } from './cache';

export interface Article {
  source_type: string;
  original_title: string;
  generated_title?: string;
  original_url: string;
  published_at: string | null;
  author?: string;
  category?: string;
  content_snippet: string;
  summary?: string;
  clickbait_score?: number;
  is_clickbait?: boolean;
  image_url?: string;
}

const FRESHNESS_HOURS = parseInt(process.env.NEWS_FRESHNESS_HOURS || '72', 10);

const DEFAULT_TOPICS = [
  'technology',
  'finance',
  'AI artificial intelligence',
  'world news',
];

function isFresh(publishedAt: string | null): boolean {
  if (!publishedAt) return true;
  const pub = new Date(publishedAt);
  const cutoff = new Date(Date.now() - FRESHNESS_HOURS * 60 * 60 * 1000);
  return pub >= cutoff;
}

function parseRssDate(dateStr: string): string | null {
  try {
    return new Date(dateStr).toISOString();
  } catch {
    return null;
  }
}

// Simple RSS XML parser (no external dependency needed for server-side)
function parseRssXml(xml: string): Array<{
  title: string;
  link: string;
  pubDate: string | null;
  description: string;
  author: string;
}> {
  const items: Array<{
    title: string;
    link: string;
    pubDate: string | null;
    description: string;
    author: string;
  }> = [];

  const itemRegex = /<item>([\s\S]*?)<\/item>/g;
  let match;
  while ((match = itemRegex.exec(xml)) !== null) {
    const itemXml = match[1];
    const getTag = (tag: string) => {
      const m = new RegExp(`<${tag}[^>]*>(?:<!\\[CDATA\\[)?(.*?)(?:\\]\\]>)?<\\/${tag}>`, 's').exec(itemXml);
      return m ? m[1].trim() : '';
    };
    items.push({
      title: getTag('title'),
      link: getTag('link'),
      pubDate: parseRssDate(getTag('pubDate')),
      description: getTag('description'),
      author: getTag('author') || getTag('dc:creator'),
    });
  }
  return items;
}

export async function fetchGoogleNews(
  topics?: string[]
): Promise<Article[]> {
  const topicList = topics?.length ? topics : DEFAULT_TOPICS;
  const cacheKey = makeCacheKey('google_news', { topics: topicList.sort() });
  const cached = cacheGet<Article[]>(cacheKey);
  if (cached) return cached;

  const allArticles: Article[] = [];

  const fetches = topicList.map(async (topic) => {
    const query = encodeURIComponent(topic);
    const url = `https://news.google.com/rss/search?q=${query}&hl=en-US&gl=US&ceid=US:en`;
    try {
      const resp = await fetch(url, {
        headers: { 'User-Agent': 'ClosedLoop/1.0 NewsAggregator' },
        signal: AbortSignal.timeout(15000),
      });
      if (!resp.ok) return;
      const xml = await resp.text();
      const items = parseRssXml(xml);
      for (const item of items) {
        if (!isFresh(item.pubDate)) continue;
        allArticles.push({
          source_type: 'google_news',
          original_title: item.title,
          original_url: item.link,
          published_at: item.pubDate,
          author: item.author || undefined,
          category: topic,
          content_snippet: item.description,
        });
      }
    } catch (e) {
      console.warn(`Failed to fetch Google News for "${topic}":`, e);
    }
  });

  await Promise.all(fetches);

  // Deduplicate by URL
  const seen = new Set<string>();
  const deduped = allArticles.filter((a) => {
    if (seen.has(a.original_url)) return false;
    seen.add(a.original_url);
    return true;
  });

  cacheSet(cacheKey, deduped);
  return deduped;
}

export async function fetchRssFeed(feedUrl: string): Promise<Article[]> {
  const cacheKey = makeCacheKey('rss', { url: feedUrl });
  const cached = cacheGet<Article[]>(cacheKey);
  if (cached) return cached;

  const articles: Article[] = [];
  try {
    const resp = await fetch(feedUrl, {
      headers: { 'User-Agent': 'ClosedLoop/1.0 NewsAggregator' },
      signal: AbortSignal.timeout(15000),
    });
    if (!resp.ok) return articles;
    const xml = await resp.text();
    const items = parseRssXml(xml);
    for (const item of items) {
      if (!isFresh(item.pubDate)) continue;
      articles.push({
        source_type: 'rss',
        original_title: item.title,
        original_url: item.link,
        published_at: item.pubDate,
        author: item.author || undefined,
        content_snippet: item.description,
      });
    }
  } catch (e) {
    console.warn(`Failed to fetch RSS "${feedUrl}":`, e);
  }

  cacheSet(cacheKey, articles);
  return articles;
}

export async function extractArticleContent(url: string): Promise<string> {
  const cacheKey = makeCacheKey('article_content', { url });
  const cached = cacheGet<string>(cacheKey);
  if (cached) return cached;

  try {
    const resp = await fetch(url, {
      headers: { 'User-Agent': 'ClosedLoop/1.0 NewsAggregator' },
      signal: AbortSignal.timeout(15000),
      redirect: 'follow',
    });
    if (!resp.ok) return '';
    const html = await resp.text();

    // Use cheerio for server-side parsing
    const cheerio = await import('cheerio');
    const $ = cheerio.load(html);

    // Remove noise
    $('script, style, nav, footer, header, aside, .ad, .advertisement').remove();

    // Try common article selectors
    const articleEl =
      $('article').first().text() ||
      $('.article-body').first().text() ||
      $('.post-content').first().text() ||
      $('main').first().text() ||
      $('body').text();

    const text = articleEl.replace(/\s+/g, ' ').trim().slice(0, 3000);
    cacheSet(cacheKey, text, 3600000); // 1 hour
    return text;
  } catch (e) {
    console.warn(`Failed to extract content from "${url}":`, e);
    return '';
  }
}
