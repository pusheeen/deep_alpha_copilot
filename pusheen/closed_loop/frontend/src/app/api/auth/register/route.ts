import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/db';
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

    const db = getDb();

    // Check existing email
    const existingEmail = db
      .prepare('SELECT id FROM users WHERE email = ?')
      .get(email);
    if (existingEmail) {
      return NextResponse.json(
        { error: 'Email already registered' },
        { status: 400 }
      );
    }

    // Check existing username
    const existingUsername = db
      .prepare('SELECT id FROM users WHERE username = ?')
      .get(username);
    if (existingUsername) {
      return NextResponse.json(
        { error: 'Username already taken' },
        { status: 400 }
      );
    }

    const hashed = await hashPassword(password);
    const result = db
      .prepare(
        'INSERT INTO users (email, username, hashed_password) VALUES (?, ?, ?)'
      )
      .run(email, username, hashed);

    const userId = result.lastInsertRowid as number;
    const token = await createToken(userId);

    return NextResponse.json({
      access_token: token,
      token_type: 'bearer',
      user: { id: userId, email, username },
    });
  } catch (e) {
    console.error('Register error:', e);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
