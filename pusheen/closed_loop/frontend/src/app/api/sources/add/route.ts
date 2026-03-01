import { NextRequest, NextResponse } from 'next/server';
import { getUserIdFromHeaders } from '@/lib/auth';
import { getDb } from '@/lib/db';

export async function POST(req: NextRequest) {
  const userId = await getUserIdFromHeaders(req.headers);
  if (!userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  const { source_type, name, config = {} } = await req.json();

  if (!source_type || !name) {
    return NextResponse.json(
      { error: 'source_type and name are required' },
      { status: 400 }
    );
  }

  const db = getDb();
  const result = db
    .prepare(
      'INSERT INTO user_sources (user_id, source_type, name, config) VALUES (?, ?, ?, ?)'
    )
    .run(userId, source_type, name, JSON.stringify(config));

  return NextResponse.json({
    id: result.lastInsertRowid,
    source_type,
    name,
    config,
  });
}

export async function DELETE(req: NextRequest) {
  const userId = await getUserIdFromHeaders(req.headers);
  if (!userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  const { searchParams } = new URL(req.url);
  const sourceId = searchParams.get('id');
  if (!sourceId) {
    return NextResponse.json({ error: 'id is required' }, { status: 400 });
  }

  const db = getDb();
  const result = db
    .prepare('DELETE FROM user_sources WHERE id = ? AND user_id = ?')
    .run(parseInt(sourceId, 10), userId);

  if (result.changes === 0) {
    return NextResponse.json({ error: 'Source not found' }, { status: 404 });
  }

  return NextResponse.json({ deleted: true });
}
