import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/context/AuthContext';

export const metadata: Metadata = {
  title: 'Closed Loop — News Without the Noise',
  description:
    'AI-powered news aggregator that cuts through clickbait and gives you TL;DR summaries from Google News, emails, and bookmarks.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body className="flex min-h-screen flex-col bg-gray-50 text-gray-900 antialiased">
        <AuthProvider>
          <div className="flex min-h-screen flex-col">
            {children}
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
