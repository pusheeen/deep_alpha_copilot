/**
 * Simple in-memory cache with TTL.
 * Works across serverless invocations on the same instance (warm starts).
 */

interface CacheEntry<T> {
  value: T;
  expiresAt: number;
}

const store = new Map<string, CacheEntry<unknown>>();

const DEFAULT_TTL = parseInt(process.env.CACHE_TTL_SECONDS || '900', 10) * 1000;

export function cacheGet<T>(key: string): T | null {
  const entry = store.get(key);
  if (!entry) return null;
  if (Date.now() > entry.expiresAt) {
    store.delete(key);
    return null;
  }
  return entry.value as T;
}

export function cacheSet<T>(key: string, value: T, ttlMs?: number): void {
  store.set(key, {
    value,
    expiresAt: Date.now() + (ttlMs || DEFAULT_TTL),
  });
}

export function cacheDelete(key: string): void {
  store.delete(key);
}

export function cacheClear(): void {
  store.clear();
}

export function makeCacheKey(prefix: string, params?: Record<string, unknown>): string {
  if (!params) return prefix;
  return `${prefix}:${JSON.stringify(params, Object.keys(params).sort())}`;
}
