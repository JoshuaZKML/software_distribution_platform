'use client';

import { useMyLicenses } from '@/lib/hooks/useLicenses';
import { Skeleton } from '@/components/ui/Skeleton';
import { Button } from '@/components/ui/Button';
import Link from 'next/link';

export default function LicensesPage() {
  const { data, isLoading, error } = useMyLicenses();

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
        <div className="text-red-500">Error loading licenses</div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">My Licenses</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white dark:bg-slate-800 p-4 rounded-lg shadow">
          <p className="text-sm text-gray-500 dark:text-gray-400">Total</p>
          <p className="text-2xl font-bold">{data.summary.total}</p>
        </div>
        <div className="bg-white dark:bg-slate-800 p-4 rounded-lg shadow">
          <p className="text-sm text-gray-500 dark:text-gray-400">Active</p>
          <p className="text-2xl font-bold text-green-600">{data.summary.active}</p>
        </div>
        <div className="bg-white dark:bg-slate-800 p-4 rounded-lg shadow">
          <p className="text-sm text-gray-500 dark:text-gray-400">Expiring Soon</p>
          <p className="text-2xl font-bold text-yellow-600">{data.summary.expiring_soon}</p>
        </div>
      </div>

      <div className="space-y-6">
        {data.licenses_by_software.map((group) => (
          <div key={group.software_slug} className="bg-white dark:bg-slate-800 rounded-lg shadow overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 dark:bg-slate-700 border-b dark:border-slate-600">
              <h2 className="font-semibold text-lg">{group.software_name}</h2>
            </div>
            <div className="divide-y dark:divide-slate-700">
              {group.licenses.map((license) => (
                <div key={license.id} className="p-4 flex items-center justify-between">
                  <div>
                    <p className="font-mono text-sm">{license.human_code}</p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Status: <span className={ont-medium }>{license.status}</span>
                      {' Â· '}Expires: {license.expires_at ? new Date(license.expires_at).toLocaleDateString() : 'Never'}
                    </p>
                  </div>
                  <div className="space-x-2">
                    <Link href={/licenses/}>
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
