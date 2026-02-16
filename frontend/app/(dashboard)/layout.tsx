'use client';

import { useAuth } from '@/lib/hooks/useAuth';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { SideNav } from '@/components/layout/SideNav';
import { TopBar } from '@/components/layout/TopBar';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push('/login');
    }
  }, [user, isLoading, router]);

  if (isLoading) return null;

  return (
    <div className="flex h-screen">
      <SideNav />
      <div className="flex-1 flex flex-col">
        <TopBar />
        <main className="flex-1 overflow-auto bg-gray-50 dark:bg-slate-900">
          {children}
        </main>
      </div>
    </div>
  );
}
