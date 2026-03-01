import { NextRequest, NextResponse } from 'next/server';
import { getUserIdFromHeaders } from '@/lib/auth';
import { fetchGoogleNews, fetchRssFeed } from '@/lib/news-fetcher';
import { batchSummarize } from '@/lib/summarizer';

export async function GET(req: NextRequest) {
  const userId = await getUserIdFromHeaders(req.headers);
  if (!userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  const { searchParams } = new URL(req.url);
  const topics = searchParams.get('topics');
  const limit = Math.min(parseInt(searchParams.get('limit') || '20', 10), 100);
  const summarize = searchParams.get('summarize') !== 'false';

  const topicList = topics
    ? topics.split(',').map((t) => t.trim()).filter(Boolean)
    : undefined;

  let articles = await fetchGoogleNews(topicList);

  // Sort newest first
  articles.sort((a, b) => {
    const da = a.published_at ? new Date(a.published_at).getTime() : 0;
    const db = b.published_at ? new Date(b.published_at).getTime() : 0;
    return db - da;
  });

  articles = articles.slice(0, limit);

  if (summarize && articles.length > 0) {
    articles = await batchSummarize(articles);
  }

  return NextResponse.json({ articles, total: articles.length });
}

export async function POST(req: NextRequest) {
  const userId = await getUserIdFromHeaders(req.headers);
  if (!userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  const body = await req.json();
  const {
    topics,
    rss_feeds,
    summarize = true,
    limit = 30,
  } = body;

  let allArticles = await fetchGoogleNews(topics);

  // Fetch custom RSS feeds
  if (rss_feeds?.length) {
    const rssResults = await Promise.all(
      rss_feeds.map((url: string) => fetchRssFeed(url))
    );
    for (const rssArticles of rssResults) {
      allArticles.push(...rssArticles);
    }
  }

  // Sort newest first
  allArticles.sort((a, b) => {
    const da = a.published_at ? new Date(a.published_at).getTime() : 0;
    const db = b.published_at ? new Date(b.published_at).getTime() : 0;
    return db - da;
  });

  allArticles = allArticles.slice(0, limit);

  if (summarize && allArticles.length > 0) {
    allArticles = await batchSummarize(allArticles);
  }

  return NextResponse.json({
    articles: allArticles,
    total: allArticles.length,
  });
}
