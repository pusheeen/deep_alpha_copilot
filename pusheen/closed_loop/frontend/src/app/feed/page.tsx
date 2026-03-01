'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { useNewsFeed } from '@/hooks/useNewsFeed';
import Navbar from '@/components/Navbar';
import SearchBox from '@/components/SearchBox';
import ArticleCard from '@/components/ArticleCard';
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

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace('/login');
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    if (user) {
      fetchFeed({ limit: 25 });
    }
  }, [user, fetchFeed]);

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    setActiveTopic(null);
    fetchFeed({ search: query, limit: 25 });
  };

  const handleTopicClick = (topic: string) => {
    if (activeTopic === topic) {
      setActiveTopic(null);
      setSearchQuery('');
      fetchFeed({ limit: 25 });
    } else {
      setActiveTopic(topic);
      setSearchQuery('');
      fetchFeed({ topics: topic.toLowerCase(), limit: 25 });
    }
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
        {/* Search */}
        <div className="mb-4">
          <SearchBox onSearch={handleSearch} isLoading={isLoading} />
        </div>

        {/* Quick topic pills */}
        <div className="mb-6 flex flex-wrap gap-2">
          {QUICK_TOPICS.map((topic) => (
            <button
              key={topic}
              onClick={() => handleTopicClick(topic)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                activeTopic === topic
                  ? 'border-brand-500 bg-brand-50 text-brand-700'
                  : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300 hover:bg-gray-50'
              }`}
            >
              {topic}
            </button>
          ))}
        </div>

        {/* Active filter label */}
        {(activeTopic || searchQuery) && (
          <div className="mb-4 flex items-center gap-2 text-sm text-gray-500">
            <span>
              {searchQuery
                ? `Results for "${searchQuery}"`
                : `Showing: ${activeTopic}`}
            </span>
            <button
              onClick={() => {
                setActiveTopic(null);
                setSearchQuery('');
                fetchFeed({ limit: 25 });
              }}
              className="text-brand-600 hover:text-brand-700"
            >
              Clear
            </button>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 p-4 text-sm text-red-600">
            {error}
          </div>
        )}

        {/* Loading */}
        {isLoading && <LoadingSpinner text="Fetching & summarizing news..." />}

        {/* Articles */}
        {!isLoading && articles.length > 0 && (
          <div className="space-y-3">
            {articles.map((article, i) => (
              <ArticleCard key={`${article.original_url}-${i}`} article={article} />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && articles.length === 0 && !error && (
          <div className="py-12 text-center text-sm text-gray-400">
            No articles found. Try a different search or topic.
          </div>
        )}
      </main>
    </div>
  );
}
