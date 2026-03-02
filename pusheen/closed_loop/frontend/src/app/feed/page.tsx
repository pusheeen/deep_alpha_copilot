'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { useNewsFeed } from '@/hooks/useNewsFeed';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import SearchBox from '@/components/SearchBox';
import ArticleCard from '@/components/ArticleCard';
import ArticleSkeleton from '@/components/ArticleSkeleton';
import LoadingSpinner from '@/components/LoadingSpinner';

const QUICK_TOPICS = [
  'Technology',
  'Finance',
  'AI',
  'World News',
  'Science',
  'Crypto',
  'Climate',
  'Health',
];

export default function FeedPage() {
  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const { articles, isLoading, error, fetchFeed } = useNewsFeed();
  const [activeTopic, setActiveTopic] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    if (!authLoading) {
      doFetch({ limit: 25 });
    }
  }, [authLoading]); // eslint-disable-line react-hooks/exhaustive-deps

  const doFetch = async (opts: Parameters<typeof fetchFeed>[0]) => {
    await fetchFeed(opts);
    setLastUpdated(new Date());
  };

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    setActiveTopic(null);
    doFetch({ search: query, limit: 25 });
  };

  const handleTopicClick = (topic: string) => {
    if (activeTopic === topic) {
      setActiveTopic(null);
      setSearchQuery('');
      doFetch({ limit: 25 });
    } else {
      setActiveTopic(topic);
      setSearchQuery('');
      doFetch({ topics: topic.toLowerCase(), limit: 25 });
    }
  };

  const handleRefresh = () => {
    if (activeTopic) {
      doFetch({ topics: activeTopic.toLowerCase(), limit: 25 });
    } else if (searchQuery) {
      doFetch({ search: searchQuery, limit: 25 });
    } else {
      doFetch({ limit: 25 });
    }
  };

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />

      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-6" role="main">
        <section aria-label="Search and filters">
          {/* Search */}
          <div className="mb-4">
            <SearchBox onSearch={handleSearch} isLoading={isLoading} />
          </div>

          {/* Quick topic pills */}
          <div
            className="mb-6 flex gap-2 overflow-x-auto pb-1 scrollbar-hide"
            role="group"
            aria-label="Quick topic filters"
          >
            {QUICK_TOPICS.map((topic) => (
              <button
                key={topic}
                onClick={() => handleTopicClick(topic)}
                aria-pressed={activeTopic === topic}
                className={`shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition ${
                  activeTopic === topic
                    ? 'border-brand-500 bg-brand-50 text-brand-700'
                    : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300 hover:bg-gray-50'
                }`}
              >
                {topic}
              </button>
            ))}
          </div>
        </section>

        {/* Active filter + refresh */}
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            {(activeTopic || searchQuery) && (
              <>
                <span>
                  {searchQuery
                    ? `Results for "${searchQuery}"`
                    : `Showing: ${activeTopic}`}
                </span>
                <button
                  onClick={() => {
                    setActiveTopic(null);
                    setSearchQuery('');
                    doFetch({ limit: 25 });
                  }}
                  className="text-brand-600 hover:text-brand-700"
                  aria-label="Clear filter"
                >
                  Clear
                </button>
              </>
            )}
          </div>

          <div className="flex items-center gap-3">
            {lastUpdated && (
              <span className="text-xs text-gray-400">
                Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
            <button
              onClick={handleRefresh}
              disabled={isLoading}
              className="flex items-center gap-1 rounded-lg border border-gray-200 px-2.5 py-1 text-xs text-gray-500 hover:bg-gray-50 disabled:opacity-50"
              aria-label="Refresh news feed"
            >
              <svg className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M4 4v5h5M20 20v-5h-5" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M20.49 9A9 9 0 0 0 5.64 5.64L4 4m16 16l-1.64-1.64A9 9 0 0 1 3.51 15" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Refresh
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div
            className="mb-4 flex items-center justify-between rounded-lg bg-red-50 p-4 text-sm text-red-600"
            role="alert"
          >
            <span>{error}</span>
            <button
              onClick={handleRefresh}
              className="ml-3 rounded-md bg-red-100 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-200"
            >
              Retry
            </button>
          </div>
        )}

        {/* Loading skeletons */}
        {isLoading && (
          <div className="space-y-3" aria-live="polite">
            {[1, 2, 3, 4, 5].map((i) => (
              <ArticleSkeleton key={i} />
            ))}
          </div>
        )}

        {/* Articles */}
        {!isLoading && articles.length > 0 && (
          <section className="space-y-3" aria-label="News articles" aria-live="polite">
            <p className="text-xs text-gray-400">{articles.length} articles</p>
            {articles.map((article, i) => (
              <ArticleCard key={`${article.original_url}-${i}`} article={article} />
            ))}
          </section>
        )}

        {/* Empty state */}
        {!isLoading && articles.length === 0 && !error && (
          <div className="flex flex-col items-center py-16 text-center" role="status">
            <svg className="mb-4 h-16 w-16 text-gray-200" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" aria-hidden="true">
              <path d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 12h10" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <h3 className="mb-1 text-sm font-medium text-gray-600">No articles found</h3>
            <p className="mb-4 text-sm text-gray-400">
              Try a different search or topic, or add more sources.
            </p>
            <button
              onClick={handleRefresh}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
            >
              Refresh feed
            </button>
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}
