'use client';

import { useState, useCallback } from 'react';
import { useAuth } from '@/context/AuthContext';

export interface Article {
  source_type: string;
  original_title: string;
  generated_title?: string;
  original_url: string;
  published_at: string | null;
  author?: string;
  category?: string;
  content_snippet: string;
  summary?: string;
  clickbait_score?: number;
  is_clickbait?: boolean;
}

export function useNewsFeed() {
  const { token } = useAuth();
  const [articles, setArticles] = useState<Article[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchFeed = useCallback(
    async (options?: { topics?: string; limit?: number; search?: string }) => {
      if (!token) return;
      setIsLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams();
        const topicsOrSearch = options?.search || options?.topics;
        if (topicsOrSearch) params.set('topics', topicsOrSearch);
        if (options?.limit) params.set('limit', String(options.limit));

        const res = await fetch(`/api/news/feed?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.error || 'Failed to fetch news');
        }

        const data = await res.json();
        setArticles(data.articles);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    },
    [token]
  );

  return { articles, isLoading, error, fetchFeed };
}
