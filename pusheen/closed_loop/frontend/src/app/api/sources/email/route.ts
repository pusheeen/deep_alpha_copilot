import { NextRequest, NextResponse } from 'next/server';
import { getUserIdFromHeaders } from '@/lib/auth';
import { batchSummarize } from '@/lib/summarizer';
import { Article } from '@/lib/news-fetcher';

function parseEmailHtml(html: string, sender: string, subject: string): Article[] {
  // Use cheerio for HTML parsing on the server
  const cheerio = require('cheerio');
  const $ = cheerio.load(html);
  const articles: Article[] = [];
  const seen = new Set<string>();

  $('a[href]').each((_: number, el: any) => {
    const href = $(el).attr('href') || '';
    const skipPatterns = [
      'unsubscribe', 'mailto:', 'facebook.com', 'twitter.com',
      'linkedin.com', 'instagram.com', '#', 'javascript:',
    ];
    if (skipPatterns.some((p) => href.toLowerCase().includes(p))) return;

    const title = $(el).text().trim();
    if (title.length < 10) return;
    if (seen.has(href)) return;
    seen.add(href);

    const parent = $(el).closest('td, div, li, p');
    const snippet = parent.length ? parent.text().trim().slice(0, 500) : title;

    articles.push({
      source_type: 'email',
      original_title: title,
      original_url: href,
      content_snippet: snippet,
      author: sender,
      published_at: new Date().toISOString(),
      category: subject ? `Email: ${subject}` : 'Email Newsletter',
    });
  });

  return articles;
}

export async function POST(req: NextRequest) {
  const userId = await getUserIdFromHeaders(req.headers);
  if (!userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  const { content, content_type = 'html', sender = '', subject = '', summarize = true } =
    await req.json();

  if (!content) {
    return NextResponse.json(
      { error: 'Email content is required' },
      { status: 400 }
    );
  }

  let articles: Article[];
  if (content_type === 'html') {
    articles = parseEmailHtml(content, sender, subject);
  } else {
    // Plain text: extract URLs
    const urlRegex = /https?:\/\/[^\s<>"]+/g;
    const urls = content.match(urlRegex) || [];
    articles = urls
      .filter((url: string) => !['unsubscribe', 'mailto:'].some((s) => url.includes(s)))
      .map((url: string) => ({
        source_type: 'email' as const,
        original_title: subject || url,
        original_url: url,
        content_snippet: '',
        author: sender,
        published_at: new Date().toISOString(),
        category: subject ? `Email: ${subject}` : 'Email Newsletter',
      }));
  }

  if (summarize && articles.length > 0) {
    articles = await batchSummarize(articles.slice(0, 20));
  }

  return NextResponse.json({ articles, total: articles.length });
}
