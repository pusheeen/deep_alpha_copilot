'use client';

import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';

export default function Navbar() {
  const { user, logout } = useAuth();

  return (
    <nav
      className="sticky top-0 z-50 border-b border-gray-200 bg-white/80 backdrop-blur-md"
      role="navigation"
      aria-label="Main navigation"
    >
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link
          href="/feed"
          className="flex items-center gap-2 text-lg font-bold tracking-tight text-gray-900"
          aria-label="Sift — go to home"
        >
          <svg className="h-6 w-6 text-brand-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M3 4h18l-7 8v6l-4 2V12L3 4z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Sift
        </Link>

        <div className="flex items-center gap-4">
          {user ? (
            <>
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
              <span className="text-sm text-gray-400" aria-label={`Logged in as ${user.username}`}>
                {user.username}
              </span>
              <button
                onClick={logout}
                className="rounded-md border border-gray-200 px-3 py-1 text-sm text-gray-600 hover:bg-gray-50"
                aria-label="Log out"
              >
                Log out
              </button>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                Log in
              </Link>
              <Link
                href="/register"
                className="rounded-md bg-brand-600 px-3 py-1 text-sm font-medium text-white hover:bg-brand-700"
              >
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
