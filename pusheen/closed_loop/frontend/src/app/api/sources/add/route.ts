import { NextRequest, NextResponse } from 'next/server';
import { getUserIdFromHeaders } from '@/lib/auth';
import { getStore } from '@/lib/db';

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

  const store = getStore();
  const source = store.insertSource(userId, source_type, name, config);

  return NextResponse.json({
    id: source.id,
    source_type: source.source_type,
    name: source.name,
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

  const store = getStore();
  const deleted = store.deleteSource(parseInt(sourceId, 10), userId);

  if (!deleted) {
    return NextResponse.json({ error: 'Source not found' }, { status: 404 });
  }

  return NextResponse.json({ deleted: true });
}
