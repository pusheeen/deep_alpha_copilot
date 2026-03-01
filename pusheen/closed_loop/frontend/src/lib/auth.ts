import { SignJWT, jwtVerify } from 'jose';
import bcrypt from 'bcryptjs';

const SECRET = new TextEncoder().encode(
  process.env.JWT_SECRET || 'dev-secret-key-change-me'
);

export async function hashPassword(password: string): Promise<string> {
  return bcrypt.hashSync(password, 10);
}

export async function verifyPassword(
  password: string,
  hash: string
): Promise<boolean> {
  return bcrypt.compareSync(password, hash);
}

export async function createToken(userId: number): Promise<string> {
  return new SignJWT({ sub: String(userId) })
    .setProtectedHeader({ alg: 'HS256' })
    .setExpirationTime('24h')
    .setIssuedAt()
    .sign(SECRET);
}

export async function verifyToken(
  token: string
): Promise<{ sub: string } | null> {
  try {
    const { payload } = await jwtVerify(token, SECRET);
    return payload as { sub: string };
  } catch {
    return null;
  }
}

export function getTokenFromHeaders(
  headers: Headers
): string | null {
  const auth = headers.get('authorization');
  if (!auth) return null;
  if (auth.startsWith('Bearer ')) return auth.slice(7);
  return auth;
}

export async function getUserIdFromHeaders(
  headers: Headers
): Promise<number | null> {
  const token = getTokenFromHeaders(headers);
  if (!token) return null;
  const payload = await verifyToken(token);
  if (!payload?.sub) return null;
  return parseInt(payload.sub, 10);
}
