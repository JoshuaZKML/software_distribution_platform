import { useQuery } from '@tanstack/react-query';

export interface DashboardStats {
  totals: {
    users: number;
    paid_users: number;
    revenue: string;
    licenses_activated: number;
    abuse_attempts: number;
  };
  last_30_days: {
    active_users: number;
    new_users: number;
    revenue: string;
  };
  latest_daily?: {
    date: string;
    total_users: number;
    active_users: number;
    new_users: number;
    total_sales: string;
    total_orders: number;
    licenses_activated: number;
    licenses_expired: number;
    total_usage_events: number;
    abuse_attempts: number;
  };
  cohorts?: Array<{
    cohort_date: string;
    period: string;
    period_number: number;
    retention_rate: number;
  }>;
  snapshot_time?: string;
}

export function useDashboardStats() {
  return useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: async (): Promise<DashboardStats> => {
      // Mock data for development
      return {
        totals: {
          users: 15000,
          paid_users: 8200,
          revenue: "125000.00",
          licenses_activated: 11000,
          abuse_attempts: 456,
        },
        last_30_days: {
          active_users: 5400,
          new_users: 870,
          revenue: "38500.00",
        },
        latest_daily: {
          date: new Date().toISOString().split('T')[0],
          total_users: 15000,
          active_users: 8900,
          new_users: 320,
          total_sales: "42500.00",
          total_orders: 1250,
          licenses_activated: 980,
          licenses_expired: 45,
          total_usage_events: 15800,
          abuse_attempts: 23,
        },
        cohorts: [
          {
            cohort_date: '2026-01-01',
            period: 'week',
            period_number: 1,
            retention_rate: 60.0,
          },
          {
            cohort_date: '2026-01-01',
            period: 'week',
            period_number: 2,
            retention_rate: 45.0,
          },
        ],
        snapshot_time: new Date().toISOString(),
      };
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}