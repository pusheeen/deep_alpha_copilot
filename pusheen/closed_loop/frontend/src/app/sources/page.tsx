'use client';

import { useEffect, useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
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
  const [toast, setToast] = useState<string | null>(null);

  // Add source form
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
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

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
        source_type: 'rss',
        name: sourceName,
        config: { url: sourceUrl },
      }),
    });
    setShowAddForm(false);
    setSourceName('');
    setSourceUrl('');
    fetchSources();
    showToast('RSS feed added');
  };

  const handleDeleteSource = async (id: number) => {
    if (!token) return;
    await fetch(`/api/sources/add?id=${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    fetchSources();
    showToast('Source removed');
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
      showToast(`Imported ${data.articles?.length || 0} articles from email`);
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
      showToast(`Imported ${data.bookmarks_imported || 0} bookmarks`);
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
    <div className="flex min-h-screen flex-col">
      <Navbar />

      {/* Toast notification */}
      {toast && (
        <div
          className="fixed right-4 top-20 z-50 rounded-lg bg-gray-900 px-4 py-2.5 text-sm text-white shadow-lg"
          role="status"
          aria-live="polite"
        >
          {toast}
        </div>
      )}

      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-6" role="main">
        <h1 className="mb-6 text-xl font-bold">Manage Sources</h1>

        {/* Action buttons */}
        <div className="mb-6 flex flex-wrap gap-3" role="group" aria-label="Add source actions">
          <button
            onClick={() => {
              setShowAddForm(!showAddForm);
              setShowEmailForm(false);
              setShowBookmarkUpload(false);
            }}
            aria-expanded={showAddForm}
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
            aria-expanded={showEmailForm}
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
            aria-expanded={showBookmarkUpload}
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
            aria-label="Add RSS feed"
          >
            <h3 className="mb-3 text-sm font-semibold">Add RSS Feed</h3>
            <label htmlFor="rss-name" className="mb-1 block text-xs font-medium text-gray-600">Feed name</label>
            <input
              id="rss-name"
              type="text"
              placeholder="e.g. TechCrunch"
              value={sourceName}
              onChange={(e) => setSourceName(e.target.value)}
              required
              aria-required="true"
              className="mb-3 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
            />
            <label htmlFor="rss-url" className="mb-1 block text-xs font-medium text-gray-600">Feed URL</label>
            <input
              id="rss-url"
              type="url"
              placeholder="https://example.com/rss"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              required
              aria-required="true"
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
            aria-label="Import email newsletter"
          >
            <h3 className="mb-3 text-sm font-semibold">Import Email Newsletter</h3>
            <p className="mb-3 text-xs text-gray-500">
              Paste the HTML source of a newsletter email to extract articles.
            </p>
            <label htmlFor="email-sender" className="mb-1 block text-xs font-medium text-gray-600">Sender</label>
            <input
              id="email-sender"
              type="text"
              placeholder="e.g. newsletter@example.com"
              value={emailSender}
              onChange={(e) => setEmailSender(e.target.value)}
              className="mb-2 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
            />
            <label htmlFor="email-subject" className="mb-1 block text-xs font-medium text-gray-600">Subject</label>
            <input
              id="email-subject"
              type="text"
              placeholder="e.g. Weekly Digest"
              value={emailSubject}
              onChange={(e) => setEmailSubject(e.target.value)}
              className="mb-2 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
            />
            <label htmlFor="email-html" className="mb-1 block text-xs font-medium text-gray-600">Email HTML content</label>
            <textarea
              id="email-html"
              placeholder="Paste email HTML content here..."
              value={emailContent}
              onChange={(e) => setEmailContent(e.target.value)}
              required
              aria-required="true"
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
                <a href="/feed" className="underline">View in feed</a>
              </p>
            )}
          </form>
        )}

        {/* Bookmark upload */}
        {showBookmarkUpload && (
          <form
            onSubmit={handleBookmarkUpload}
            className="mb-6 rounded-xl border border-gray-200 bg-white p-5"
            aria-label="Import Chrome bookmarks"
          >
            <h3 className="mb-3 text-sm font-semibold">Import Chrome Bookmarks</h3>
            <p className="mb-3 text-xs text-gray-500">
              Export your Chrome bookmarks (Bookmarks Manager &rarr; Export) and
              upload the HTML file.
            </p>
            <label htmlFor="bookmark-file" className="mb-1 block text-xs font-medium text-gray-600">Bookmarks file</label>
            <input
              id="bookmark-file"
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
              <p className="mt-3 text-sm text-green-600" role="status">
                Imported {bookmarkCount} bookmarks!
              </p>
            )}
          </form>
        )}

        {/* Saved sources list */}
        <section className="mt-6" aria-label="Your sources">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">Your Sources</h2>
          {sources.length === 0 ? (
            <div className="flex flex-col items-center rounded-xl border border-dashed border-gray-200 py-10 text-center">
              <svg className="mb-3 h-10 w-10 text-gray-200" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                <path d="M12 4v16m8-8H4" strokeLinecap="round" />
              </svg>
              <p className="mb-1 text-sm font-medium text-gray-500">No sources yet</p>
              <p className="text-xs text-gray-400">
                Add an RSS feed, import emails, or upload bookmarks to get started.
              </p>
            </div>
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
                    aria-label={`Remove source ${s.name}`}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      <Footer />
    </div>
  );
}
