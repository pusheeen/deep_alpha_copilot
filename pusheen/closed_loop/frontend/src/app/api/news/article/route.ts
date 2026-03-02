import { NextRequest, NextResponse } from 'next/server';
import { getUserIdFromHeaders } from '@/lib/auth';
import { extractArticleContent } from '@/lib/news-fetcher';
import { summarizeArticle } from '@/lib/summarizer';

export async function GET(req: NextRequest) {
  const userId = await getUserIdFromHeaders(req.headers);
  if (!userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  const { searchParams } = new URL(req.url);
  const url = searchParams.get('url');

  if (!url) {
    return NextResponse.json(
      { error: 'URL parameter is required' },
      { status: 400 }
    );
  }

  const content = await extractArticleContent(url);
  if (!content) {
    return NextResponse.json(
      { error: 'Could not fetch article content' },
      { status: 404 }
    );
  }

  const result = await summarizeArticle('', content, url);

  return NextResponse.json({
    url,
    content_snippet: content.slice(0, 1000),
    ...result,
  });
}
