'use client';

export default function ArticleSkeleton() {
  return (
    <div
      className="animate-pulse rounded-xl border border-gray-100 bg-white p-5"
      role="status"
      aria-label="Loading article"
    >
      <div className="mb-3 flex items-center gap-2">
        <div className="h-5 w-20 rounded-full bg-gray-100" />
        <div className="h-5 w-16 rounded-full bg-gray-100" />
        <div className="ml-auto h-4 w-12 rounded bg-gray-100" />
      </div>
      <div className="mb-2 h-5 w-4/5 rounded bg-gray-100" />
      <div className="mb-3 space-y-2">
        <div className="h-4 w-full rounded bg-gray-50" />
        <div className="h-4 w-3/4 rounded bg-gray-50" />
      </div>
      <div className="flex gap-3">
        <div className="h-3 w-16 rounded bg-gray-50" />
        <div className="h-3 w-20 rounded bg-gray-50" />
      </div>
      <span className="sr-only">Loading article...</span>
    </div>
  );
}
