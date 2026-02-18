'use client';

import { useAuth } from '@/lib/hooks/useAuth';
import { useDashboardStats } from '@/lib/hooks/useDashboardStats';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { TopBar } from '@/components/layout/TopBar';
import { Sidebar } from '@/components/layout/Sidebar';

export default function DashboardPage() {
  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const { data: stats, isLoading: statsLoading, error } = useDashboardStats();

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
    }
  }, [user, authLoading, router]);

  if (authLoading || statsLoading) {
    return (
      <div className="flex h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <TopBar />
          <main className="p-6">
            <Skeleton className="h-8 w-64 mb-4" />
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-24 rounded-lg" />
              ))}
            </div>
          </main>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <TopBar />
          <main className="p-6">
            <div className="text-red-500">Error loading dashboard</div>
          </main>
        </div>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <TopBar />
        <main className="p-6 overflow-auto">
          <h1 className="text-2xl font-bold mb-4">Dashboard</h1>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Welcome back, {user?.email}
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="p-4">
              <p className="text-sm text-gray-600 dark:text-gray-400">Total Users</p>
              <p className="text-2xl font-bold">{stats.totals.users.toLocaleString()}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-gray-600 dark:text-gray-400">Active Users (30d)</p>
              <p className="text-2xl font-bold">{stats.last_30_days.active_users.toLocaleString()}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-gray-600 dark:text-gray-400">Revenue (30d)</p>
              <p className="text-2xl font-bold">${stats.last_30_days.revenue}</p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-gray-600 dark:text-gray-400">Licenses Activated</p>
              <p className="text-2xl font-bold">{stats.totals.licenses_activated.toLocaleString()}</p>
            </Card>
          </div>

          <div className="mt-8">
            <h2 className="text-xl font-semibold mb-4">Recent Activity</h2>
            <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-4">
              <p className="text-gray-500 dark:text-gray-400">Activity feed coming soon...</p>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
