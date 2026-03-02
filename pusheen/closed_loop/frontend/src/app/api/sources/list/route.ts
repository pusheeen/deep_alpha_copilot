import { NextRequest, NextResponse } from 'next/server';
import { getUserIdFromHeaders } from '@/lib/auth';
import { getStore } from '@/lib/db';

export async function GET(req: NextRequest) {
  const userId = await getUserIdFromHeaders(req.headers);
  if (!userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  const store = getStore();
  const sources = store.getSourcesByUser(userId);

  return NextResponse.json(
    sources.map((s) => ({
      id: s.id,
      source_type: s.source_type,
      name: s.name,
      config: JSON.parse(s.config || '{}'),
      created_at: s.created_at,
    }))
  );
}
