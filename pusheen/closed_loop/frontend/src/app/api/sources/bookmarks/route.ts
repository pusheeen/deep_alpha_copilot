import { NextRequest, NextResponse } from 'next/server';
import { getUserIdFromHeaders } from '@/lib/auth';
import { getDb } from '@/lib/db';
import { batchSummarize } from '@/lib/summarizer';
import { Article } from '@/lib/news-fetcher';

function parseBookmarksHtml(html: string): Array<{
  url: string;
  title: string;
  folder: string | null;
}> {
  const cheerio = require('cheerio');
  const $ = cheerio.load(html);
  const bookmarks: Array<{ url: string; title: string; folder: string | null }> = [];

  $('a').each((_: number, el: any) => {
    const href = $(el).attr('href') || '';
    if (!href.startsWith('http://') && !href.startsWith('https://')) return;
    const title = $(el).text().trim();

    // Find parent folder
    let folder: string | null = null;
    const parentDl = $(el).closest('dl');
    if (parentDl.length) {
      const h3 = parentDl.prev('h3');
      if (h3.length) folder = h3.text().trim();
    }

    bookmarks.push({ url: href, title, folder });
  });

  return bookmarks;
}

export async function POST(req: NextRequest) {
  const userId = await getUserIdFromHeaders(req.headers);
  if (!userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  // Accept JSON with HTML content or form data
  const contentType = req.headers.get('content-type') || '';
  let html: string;

  if (contentType.includes('multipart/form-data')) {
    const formData = await req.formData();
    const file = formData.get('file') as File;
    if (!file) {
      return NextResponse.json({ error: 'File is required' }, { status: 400 });
    }
    html = await file.text();
  } else {
    try {
      const body = await req.json();
      html = body.html;
    } catch {
      return NextResponse.json(
        { error: 'Invalid JSON body' },
        { status: 400 }
      );
    }
    if (!html) {
      return NextResponse.json(
        { error: 'Bookmarks HTML content is required' },
        { status: 400 }
      );
    }
  }

  const bookmarks = parseBookmarksHtml(html);

  // Save to DB
  const db = getDb();
  const insert = db.prepare(
    'INSERT INTO bookmarks (user_id, url, title, folder) VALUES (?, ?, ?, ?)'
  );

  const insertMany = db.transaction((bms: typeof bookmarks) => {
    for (const bm of bms) {
      insert.run(userId, bm.url, bm.title, bm.folder);
    }
  });
  insertMany(bookmarks);

  // Convert to articles
  const articles: Article[] = bookmarks.slice(0, 30).map((bm) => ({
    source_type: 'bookmark',
    original_title: bm.title || bm.url,
    original_url: bm.url,
    content_snippet: '',
    published_at: null,
    category: bm.folder ? `Bookmark: ${bm.folder}` : 'Bookmarks',
  }));

  return NextResponse.json({
    bookmarks_imported: bookmarks.length,
    articles,
  });
}
