'use client';

import { useEffect, useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Navbar from '@/components/Navbar';
import LoadingSpinner from '@/components/LoadingSpinner';

interface Source {
  id: number;
  source_type: string;
  name: string;
  config: Record<string, unknown>;
}

export default function SourcesPage() {
  const { user, token, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showEmailForm, setShowEmailForm] = useState(false);
  const [showBookmarkUpload, setShowBookmarkUpload] = useState(false);

  // Add source form
  const [sourceType, setSourceType] = useState('rss');
  const [sourceName, setSourceName] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');

  // Email form
  const [emailContent, setEmailContent] = useState('');
  const [emailSender, setEmailSender] = useState('');
  const [emailSubject, setEmailSubject] = useState('');
  const [emailResults, setEmailResults] = useState<unknown[]>([]);

  // Bookmark
  const [bookmarkFile, setBookmarkFile] = useState<File | null>(null);
  const [bookmarkCount, setBookmarkCount] = useState(0);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace('/login');
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    if (token) fetchSources();
  }, [token]);

  const fetchSources = async () => {
    if (!token) return;
    const res = await fetch('/api/sources/list', {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) setSources(await res.json());
  };

  const handleAddSource = async (e: FormEvent) => {
    e.preventDefault();
    if (!token) return;
    await fetch('/api/sources/add', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        source_type: sourceType,
        name: sourceName,
        config: { url: sourceUrl },
      }),
    });
    setShowAddForm(false);
    setSourceName('');
    setSourceUrl('');
    fetchSources();
  };

  const handleDeleteSource = async (id: number) => {
    if (!token) return;
    await fetch(`/api/sources/add?id=${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    fetchSources();
  };

  const handleEmailImport = async (e: FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setLoading(true);
    const res = await fetch('/api/sources/email', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        content: emailContent,
        content_type: 'html',
        sender: emailSender,
        subject: emailSubject,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      setEmailResults(data.articles || []);
    }
    setLoading(false);
  };

  const handleBookmarkUpload = async (e: FormEvent) => {
    e.preventDefault();
    if (!token || !bookmarkFile) return;
    setLoading(true);

    const html = await bookmarkFile.text();
    const res = await fetch('/api/sources/bookmarks', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ html }),
    });

    if (res.ok) {
      const data = await res.json();
      setBookmarkCount(data.bookmarks_imported || 0);
    }
    setLoading(false);
  };

  if (authLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <Navbar />

      <main className="mx-auto max-w-3xl px-4 py-6">
        <h1 className="mb-6 text-xl font-bold">Manage Sources</h1>

        {/* Action buttons */}
        <div className="mb-6 flex flex-wrap gap-3">
          <button
            onClick={() => {
              setShowAddForm(!showAddForm);
              setShowEmailForm(false);
              setShowBookmarkUpload(false);
            }}
            className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            + Add RSS Feed
          </button>
          <button
            onClick={() => {
              setShowEmailForm(!showEmailForm);
              setShowAddForm(false);
              setShowBookmarkUpload(false);
            }}
            className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            + Import Email Newsletter
          </button>
          <button
            onClick={() => {
              setShowBookmarkUpload(!showBookmarkUpload);
              setShowAddForm(false);
              setShowEmailForm(false);
            }}
            className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            + Import Chrome Bookmarks
          </button>
        </div>

        {/* Add RSS form */}
        {showAddForm && (
          <form
            onSubmit={handleAddSource}
            className="mb-6 rounded-xl border border-gray-200 bg-white p-5"
          >
            <h3 className="mb-3 text-sm font-semibold">Add RSS Feed</h3>
            <input
              type="text"
              placeholder="Feed name (e.g. TechCrunch)"
              value={sourceName}
              onChange={(e) => setSourceName(e.target.value)}
              required
              className="mb-3 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
            />
            <input
              type="url"
              placeholder="RSS feed URL"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              required
              className="mb-3 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
            />
            <button
              type="submit"
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
            >
              Add
            </button>
          </form>
        )}

        {/* Email import form */}
        {showEmailForm && (
          <form
            onSubmit={handleEmailImport}
            className="mb-6 rounded-xl border border-gray-200 bg-white p-5"
          >
            <h3 className="mb-3 text-sm font-semibold">
              Import Email Newsletter
            </h3>
            <p className="mb-3 text-xs text-gray-500">
              Paste the HTML source of a newsletter email to extract articles.
            </p>
            <input
              type="text"
              placeholder="Sender"
              value={emailSender}
              onChange={(e) => setEmailSender(e.target.value)}
              className="mb-2 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
            />
            <input
              type="text"
              placeholder="Subject"
              value={emailSubject}
              onChange={(e) => setEmailSubject(e.target.value)}
              className="mb-2 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
            />
            <textarea
              placeholder="Paste email HTML content here..."
              value={emailContent}
              onChange={(e) => setEmailContent(e.target.value)}
              required
              rows={6}
              className="mb-3 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
            />
            <button
              type="submit"
              disabled={loading}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {loading ? 'Processing...' : 'Import & Summarize'}
            </button>

            {emailResults.length > 0 && (
              <p className="mt-3 text-sm text-green-600">
                Found {emailResults.length} articles from email.{' '}
                <a href="/feed" className="underline">
                  View in feed
                </a>
              </p>
            )}
          </form>
        )}

        {/* Bookmark upload */}
        {showBookmarkUpload && (
          <form
            onSubmit={handleBookmarkUpload}
            className="mb-6 rounded-xl border border-gray-200 bg-white p-5"
          >
            <h3 className="mb-3 text-sm font-semibold">
              Import Chrome Bookmarks
            </h3>
            <p className="mb-3 text-xs text-gray-500">
              Export your Chrome bookmarks (Bookmarks Manager &rarr; Export) and
              upload the HTML file.
            </p>
            <input
              type="file"
              accept=".html"
              onChange={(e) => setBookmarkFile(e.target.files?.[0] || null)}
              className="mb-3 block w-full text-sm text-gray-500 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-brand-600 hover:file:bg-brand-100"
            />
            <button
              type="submit"
              disabled={loading || !bookmarkFile}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {loading ? 'Uploading...' : 'Import'}
            </button>

            {bookmarkCount > 0 && (
              <p className="mt-3 text-sm text-green-600">
                Imported {bookmarkCount} bookmarks!
              </p>
            )}
          </form>
        )}

        {/* Saved sources list */}
        <div className="mt-6">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">
            Your Sources
          </h2>
          {sources.length === 0 ? (
            <p className="text-sm text-gray-400">
              No sources added yet. Add an RSS feed, import emails, or upload
              bookmarks.
            </p>
          ) : (
            <div className="space-y-2">
              {sources.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between rounded-lg border border-gray-100 bg-white px-4 py-3"
                >
                  <div>
                    <span className="text-sm font-medium">{s.name}</span>
                    <span className="ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
                      {s.source_type}
                    </span>
                  </div>
                  <button
                    onClick={() => handleDeleteSource(s.id)}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
