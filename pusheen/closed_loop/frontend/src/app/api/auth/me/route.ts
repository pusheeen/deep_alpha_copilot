import { NextRequest, NextResponse } from 'next/server';
import { getStore } from '@/lib/db';
import { getUserIdFromHeaders } from '@/lib/auth';

export async function GET(req: NextRequest) {
  const userId = await getUserIdFromHeaders(req.headers);
  if (!userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  const store = getStore();
  const user = store.getUserById(userId);

  if (!user) {
    return NextResponse.json({ error: 'User not found' }, { status: 404 });
  }

  return NextResponse.json({
    id: user.id,
    email: user.email,
    username: user.username,
    created_at: user.created_at,
  });
}
