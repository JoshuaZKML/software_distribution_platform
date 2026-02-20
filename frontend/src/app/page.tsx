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

  // --- Auth guard (early return before rendering any dashboard shell) ---
  useEffect(() => {
    if (!authLoading && !user) {
      router.replace('/login'); // changed from push to replace
    }
  }, [user, authLoading, router]);

  if (!authLoading && !user) {
    return null; // prevent flash of protected content
  }

  // --- Loading state ---
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

  // --- Error state ---
  if (error) {
    return (
      <div className="flex h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <TopBar />
          <main className="p-6">
            <div className="text-state-error">Error loading dashboard</div>
          </main>
        </div>
      </div>
    );
  }

  // --- No stats (fallback UI) ---
  if (!stats) {
    return (
      <div className="flex h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <TopBar />
          <main className="p-6">
            <div className="text-text-muted">No data available.</div>
          </main>
        </div>
      </div>
    );
  }

  // --- Main dashboard content ---
  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <TopBar />
        <main className="p-6 overflow-auto">
          <h1 className="text-2xl font-bold mb-4">Dashboard</h1>
          <p className="text-text-muted mb-6">
            Welcome back, {user?.email}
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="p-4">
              <p className="text-sm text-text-muted">Total Users</p>
              <p className="text-2xl font-bold">
                {stats?.totals?.users?.toLocaleString?.() ?? '0'}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-text-muted">Active Users (30d)</p>
              <p className="text-2xl font-bold">
                {stats?.last_30_days?.active_users?.toLocaleString?.() ?? '0'}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-text-muted">Revenue (30d)</p>
              <p className="text-2xl font-bold">
                ${Number(stats?.last_30_days?.revenue ?? 0).toFixed(2)}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-text-muted">Licenses Activated</p>
              <p className="text-2xl font-bold">
                {stats?.totals?.licenses_activated?.toLocaleString?.() ?? '0'}
              </p>
            </Card>
          </div>

          <div className="mt-8">
            <h2 className="text-xl font-semibold mb-4">Recent Activity</h2>
            <div className="bg-background-surface rounded-lg shadow p-4">
              <p className="text-text-muted">Activity feed coming soon...</p>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}