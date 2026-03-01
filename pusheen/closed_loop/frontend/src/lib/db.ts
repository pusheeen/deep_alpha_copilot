import Database from 'better-sqlite3';
import path from 'path';

// On Vercel serverless, only /tmp is writable. Locally use project root.
const IS_VERCEL = !!process.env.VERCEL;
const DB_DIR = IS_VERCEL ? '/tmp' : process.cwd();
const DB_PATH = path.join(DB_DIR, 'closed_loop.db');

let db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!db) {
    db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    db.pragma('foreign_keys = ON');
    initDb(db);
  }
  return db;
}

function initDb(db: Database.Database) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL,
      username TEXT UNIQUE NOT NULL,
      hashed_password TEXT NOT NULL,
      created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS user_sources (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      source_type TEXT NOT NULL,
      name TEXT NOT NULL,
      config TEXT DEFAULT '{}',
      created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS bookmarks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      url TEXT NOT NULL,
      title TEXT,
      folder TEXT,
      added_at TEXT DEFAULT (datetime('now'))
    );
  `);
}

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
  config: string;
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
