import { NextRequest, NextResponse } from 'next/server';
import { getStore } from '@/lib/db';
import { hashPassword, createToken } from '@/lib/auth';

export async function POST(req: NextRequest) {
  try {
    const { email, username, password } = await req.json();

    if (!email || !username || !password) {
      return NextResponse.json(
        { error: 'Email, username, and password are required' },
        { status: 400 }
      );
    }

    if (password.length < 6) {
      return NextResponse.json(
        { error: 'Password must be at least 6 characters' },
        { status: 400 }
      );
    }

    const store = getStore();

    if (store.getUserByEmail(email)) {
      return NextResponse.json(
        { error: 'Email already registered' },
        { status: 400 }
      );
    }

    if (store.getUserByUsername(username)) {
      return NextResponse.json(
        { error: 'Username already taken' },
        { status: 400 }
      );
    }

    const hashed = await hashPassword(password);
    const user = store.insertUser(email, username, hashed);
    const token = await createToken(user.id);

    return NextResponse.json({
      access_token: token,
      token_type: 'bearer',
      user: { id: user.id, email, username },
    });
  } catch (e) {
    console.error('Register error:', e);
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { error: 'Internal server error', detail: message },
      { status: 500 }
    );
  }
}
