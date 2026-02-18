'use client';

import { useMyLicenses } from '@/lib/hooks/useLicenses';
import { Skeleton } from '@/components/ui/Skeleton';
import { Button } from '@/components/ui/Button';
import Link from 'next/link';
import { useMemo } from 'react';

export default function LicensesPage() {
  const { data, isLoading, error } = useMyLicenses();

  // Compute summary and grouped licenses from the paginated results
  const summary = useMemo(() => {
    if (!data) return null;
    const total = data.count;
    const active = data.results.filter((l) => l.status === 'ACTIVATED').length;

    // Define "expiring soon" as within 30 days from now
    const now = new Date();
    const expiringSoon = data.results.filter((l) => {
      if (!l.expires_at) return false;
      const expiryDate = new Date(l.expires_at);
      const diffDays = Math.ceil((expiryDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
      return diffDays <= 30 && diffDays >= 0;
    }).length;

    return { total, active, expiring_soon: expiringSoon };
  }, [data]);

  const licensesBySoftware = useMemo(() => {
    if (!data) return [];
    const groups = data.results.reduce((acc, license) => {
      const softwareSlug = license.software_slug;
      if (!acc[softwareSlug]) {
        acc[softwareSlug] = {
          software_slug: softwareSlug,
          software_name: license.software_name,
          licenses: [],
        };
      }
      acc[softwareSlug].licenses.push(license);
      return acc;
    }, {} as Record<string, { software_slug: string; software_name: string; licenses: typeof data.results }>);

    return Object.values(groups);
  }, [data]);

  if (isLoading) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">My Licenses</h1>
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-32 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">My Licenses</h1>
        <div className="text-state-error">Error loading licenses</div>
      </div>
    );
  }

  if (!data || !summary) return null;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">My Licenses</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-surface p-4 rounded-lg shadow">
          <p className="text-sm text-muted-foreground">Total</p>
          <p className="text-2xl font-bold">{summary.total}</p>
        </div>
        <div className="bg-surface p-4 rounded-lg shadow">
          <p className="text-sm text-muted-foreground">Active</p>
          <p className="text-2xl font-bold text-state-success">{summary.active}</p>
        </div>
        <div className="bg-surface p-4 rounded-lg shadow">
          <p className="text-sm text-muted-foreground">Expiring Soon</p>
          <p className="text-2xl font-bold text-state-warning">{summary.expiring_soon}</p>
        </div>
      </div>

      <div className="space-y-6">
        {licensesBySoftware.map((group) => (
          <div key={group.software_slug} className="bg-surface rounded-lg shadow overflow-hidden">
            <div className="px-4 py-3 bg-background-secondary border-b border-border-subtle">
              <h2 className="font-semibold text-lg">{group.software_name}</h2>
            </div>
            <div className="divide-y divide-border-subtle">
              {group.licenses.map((license) => (
                <div key={license.id} className="p-4 flex items-center justify-between">
                  <div>
                    <p className="font-mono text-sm">{license.human_code}</p>
                    <p className="text-sm text-muted-foreground">
                      Status: <span className="font-medium">{license.status}</span>
                      {' · '}Expires: {license.expires_at ? new Date(license.expires_at).toLocaleDateString() : 'Never'}
                    </p>
                  </div>
                  <div className="space-x-2">
                    <Link href={`/licenses/${license.id}`}>
                      <Button variant="outline" size="sm">View</Button>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}