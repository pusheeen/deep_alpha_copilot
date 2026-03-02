'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';

export default function HomePage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading) {
      router.replace('/feed');
    }
  }, [user, isLoading, router]);

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="flex flex-1 items-center justify-center" role="main">
        <div
          className="h-8 w-8 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600"
          role="status"
          aria-label="Loading"
        />
      </main>
      <Footer />
    </div>
  );
}
