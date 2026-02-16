'use client';

import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api/client';
import { Skeleton } from '@/components/ui/Skeleton';
import { Button } from '@/components/ui/Button';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import Link from 'next/link';

export default function LicenseDetailPage() {
  const { id } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ['license', id],
    queryFn: async () => {
      const { data } = await apiClient.get(/licenses/activation-codes//);
      return data;
    },
  });

  if (isLoading) {
    return (
      <div className="p-6">
        <Skeleton className="h-8 w-48 mb-4" />
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="text-red-500">Error loading license</div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <Link href="/licenses" className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 mb-4">
        <ArrowLeftIcon className="h-4 w-4 mr-1" />
        Back to licenses
      </Link>
      <h1 className="text-2xl font-bold mb-4">License Details</h1>
      <pre className="bg-gray-100 dark:bg-slate-800 p-4 rounded-lg overflow-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
