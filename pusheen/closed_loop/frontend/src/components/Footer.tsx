'use client';

export default function Footer() {
  return (
    <footer className="border-t border-gray-200 bg-white" role="contentinfo">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
        <p className="text-xs text-gray-400">
          Sift — News Without the Noise
        </p>
        <div className="flex gap-4 text-xs text-gray-400">
          <span>AI-powered news aggregator</span>
        </div>
      </div>
    </footer>
  );
}
