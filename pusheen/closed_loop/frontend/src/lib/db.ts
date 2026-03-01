/**
 * Lightweight in-memory database — works on Vercel serverless, local dev,
 * Docker, etc. No native modules required.
 *
 * NOTE: Data is ephemeral on serverless (lost on cold start).
 * For production persistence, swap with Vercel Postgres / Supabase / PlanetScale.
 */

// ── Types ───────────────────────────────────────────────────────────────

export interface User {
  id: number;
  email: string;
  username: string;
  hashed_password: string;
  created_at: string;
}

export interface UserSource {
  id: number;
  user_id: number;
  source_type: string;
  name: string;
  config: string; // JSON string
  created_at: string;
}

export interface BookmarkRow {
  id: number;
  user_id: number;
  url: string;
  title: string | null;
  folder: string | null;
  added_at: string;
}

// ── In-memory store ─────────────────────────────────────────────────────

class MemoryStore {
  private users: User[] = [];
  private userSources: UserSource[] = [];
  private bookmarks: BookmarkRow[] = [];
  private nextUserId = 1;
  private nextSourceId = 1;
  private nextBookmarkId = 1;

  // ── Users ───────────────────────────────────────────────────────────

  insertUser(email: string, username: string, hashedPassword: string): User {
    const user: User = {
      id: this.nextUserId++,
      email,
      username,
      hashed_password: hashedPassword,
      created_at: new Date().toISOString(),
    };
    this.users.push(user);
    return user;
  }

  getUserByEmail(email: string): User | undefined {
    return this.users.find((u) => u.email === email);
  }

  getUserByUsername(username: string): User | undefined {
    return this.users.find((u) => u.username === username);
  }

  getUserById(id: number): User | undefined {
    return this.users.find((u) => u.id === id);
  }

  // ── Sources ─────────────────────────────────────────────────────────

  insertSource(userId: number, sourceType: string, name: string, config: Record<string, unknown>): UserSource {
    const source: UserSource = {
      id: this.nextSourceId++,
      user_id: userId,
      source_type: sourceType,
      name,
      config: JSON.stringify(config),
      created_at: new Date().toISOString(),
    };
    this.userSources.push(source);
    return source;
  }

  getSourcesByUser(userId: number): UserSource[] {
    return this.userSources.filter((s) => s.user_id === userId);
  }

  getSourceById(id: number, userId: number): UserSource | undefined {
    return this.userSources.find((s) => s.id === id && s.user_id === userId);
  }

  deleteSource(id: number, userId: number): boolean {
    const idx = this.userSources.findIndex((s) => s.id === id && s.user_id === userId);
    if (idx === -1) return false;
    this.userSources.splice(idx, 1);
    return true;
  }

  // ── Bookmarks ───────────────────────────────────────────────────────

  insertBookmark(userId: number, url: string, title: string | null, folder: string | null): BookmarkRow {
    const bookmark: BookmarkRow = {
      id: this.nextBookmarkId++,
      user_id: userId,
      url,
      title,
      folder,
      added_at: new Date().toISOString(),
    };
    this.bookmarks.push(bookmark);
    return bookmark;
  }

  getBookmarksByUser(userId: number, limit = 20): BookmarkRow[] {
    return this.bookmarks.filter((b) => b.user_id === userId).slice(0, limit);
  }
}

// Singleton — persists across requests within the same Lambda warm instance
let store: MemoryStore | null = null;

export function getStore(): MemoryStore {
  if (!store) {
    store = new MemoryStore();
  }
  return store;
}

// Backward-compatible alias
export const getDb = getStore;
