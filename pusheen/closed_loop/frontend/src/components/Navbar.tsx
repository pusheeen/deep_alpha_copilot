'use client';

import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';

export default function Navbar() {
  const { user, logout } = useAuth();

  return (
    <nav className="sticky top-0 z-50 border-b border-gray-200 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link
          href="/feed"
          className="text-lg font-bold tracking-tight text-gray-900"
        >
          Closed Loop
        </Link>

        {user && (
          <div className="flex items-center gap-4">
            <Link
              href="/feed"
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              Feed
            </Link>
            <Link
              href="/sources"
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              Sources
            </Link>
            <span className="text-sm text-gray-400">{user.username}</span>
            <button
              onClick={logout}
              className="rounded-md border border-gray-200 px-3 py-1 text-sm text-gray-600 hover:bg-gray-50"
            >
              Log out
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}
