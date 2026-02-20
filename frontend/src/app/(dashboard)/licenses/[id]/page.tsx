'use client';

import { useQuery } from '@tanstack/react-query';
import { useParams } from 'next/navigation';
import apiClient from '@/lib/api/client';
import { Card } from '@/components/ui/Card';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Skeleton } from '@/components/ui/Skeleton';

export default function LicenseDetailPage() {
  const { id } = useParams();

  const { data, isLoading, error } = useQuery({
    queryKey: ['license', id],
    queryFn: async () => {
      const { data } = await apiClient.get(`/licenses/activation-codes/${id}/`);
      return data;
    },
    enabled: !!id, // prevent fetch when id is undefined
  });

  if (isLoading) return <div className="p-8"><Skeleton className="h-32 w-full" /></div>;
  if (error) return <div className="p-8 text-state-error">Error loading license</div>;
  if (!data) return <div className="p-8">Not found</div>;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">License Details</h1>
      <Card className="p-6 space-y-4">
        <div>
          <span className="text-text-muted">Code:</span>
          <span className="ml-2 font-mono">{data.human_code}</span>
        </div>
        <div>
          <span className="text-text-muted">Software:</span>
          <span className="ml-2">{data.software_name}</span>
        </div>
        <div>
          <span className="text-text-muted">Status:</span>
          <StatusBadge variant={data.status === 'ACTIVATED' ? 'success' : 'neutral'} className="ml-2">
            {data.status}
          </StatusBadge>
        </div>
        <div>
          <span className="text-text-muted">Expires:</span>
          <span className="ml-2">{data.expires_at ? new Date(data.expires_at).toLocaleDateString() : 'Never'}</span>
        </div>
      </Card>
    </div>
  );
}