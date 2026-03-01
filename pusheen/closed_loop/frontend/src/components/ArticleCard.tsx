'use client';

import { Article } from '@/hooks/useNewsFeed';

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

function sourceLabel(type: string): string {
  switch (type) {
    case 'google_news': return 'Google News';
    case 'rss': return 'RSS';
    case 'email': return 'Email';
    case 'bookmark': return 'Bookmark';
    default: return type;
  }
}

function sourceColor(type: string): string {
  switch (type) {
    case 'google_news': return 'bg-blue-50 text-blue-700';
    case 'rss': return 'bg-orange-50 text-orange-700';
    case 'email': return 'bg-purple-50 text-purple-700';
    case 'bookmark': return 'bg-green-50 text-green-700';
    default: return 'bg-gray-50 text-gray-700';
  }
}

export default function ArticleCard({ article }: { article: Article }) {
  const displayTitle = article.generated_title || article.original_title;
  const isClickbait = article.is_clickbait;

  return (
    <a
      href={article.original_url}
      target="_blank"
      rel="noopener noreferrer"
      className="group block rounded-xl border border-gray-100 bg-white p-5 shadow-sm transition hover:border-gray-200 hover:shadow-md"
    >
      <div className="mb-3 flex items-center gap-2">
        <span
          className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${sourceColor(article.source_type)}`}
        >
          {sourceLabel(article.source_type)}
        </span>
        {article.category && (
          <span className="rounded-full bg-gray-50 px-2.5 py-0.5 text-xs text-gray-500">
            {article.category}
          </span>
        )}
        {isClickbait && (
          <span className="rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-600">
            Clickbait detected
          </span>
        )}
        <span className="ml-auto text-xs text-gray-400">
          {timeAgo(article.published_at)}
        </span>
      </div>

      <h3 className="mb-2 text-base font-semibold leading-snug text-gray-900 group-hover:text-brand-600">
        {displayTitle}
      </h3>

      {isClickbait && article.original_title !== displayTitle && (
        <p className="mb-2 text-xs italic text-gray-400 line-through">
          Original: {article.original_title}
        </p>
      )}

      {article.summary && (
        <p className="mb-3 text-sm leading-relaxed text-gray-600">
          {article.summary}
        </p>
      )}

      <div className="flex items-center gap-3 text-xs text-gray-400">
        {article.author && <span>By {article.author}</span>}
        {article.clickbait_score !== undefined && article.clickbait_score > 0 && (
          <span
            className={`${
              article.clickbait_score >= 0.6
                ? 'text-red-400'
                : article.clickbait_score >= 0.3
                  ? 'text-yellow-500'
                  : 'text-green-500'
            }`}
          >
            Clickbait: {Math.round(article.clickbait_score * 100)}%
          </span>
        )}
      </div>
    </a>
  );
}
