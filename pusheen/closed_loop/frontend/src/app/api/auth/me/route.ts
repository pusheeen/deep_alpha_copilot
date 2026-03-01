import { NextRequest, NextResponse } from 'next/server';
import { getDb, User } from '@/lib/db';
import { getUserIdFromHeaders } from '@/lib/auth';

export async function GET(req: NextRequest) {
  const userId = await getUserIdFromHeaders(req.headers);
  if (!userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  const db = getDb();
  const user = db
    .prepare('SELECT id, email, username, created_at FROM users WHERE id = ?')
    .get(userId) as Omit<User, 'hashed_password'> | undefined;

  if (!user) {
    return NextResponse.json({ error: 'User not found' }, { status: 404 });
  }

  return NextResponse.json(user);
}
