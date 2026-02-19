import { http, HttpResponse } from 'msw';
import { faker } from '@faker-js/faker';

export const dashboardHandlers = [
  http.get('/api/v1/dashboard/stats/', () => {
    return HttpResponse.json({
      latest_daily: {
        date: faker.date.recent().toISOString().split('T')[0],
        total_users: faker.number.int({ min: 1000, max: 5000 }),
        active_users: faker.number.int({ min: 500, max: 3000 }),
        new_users: faker.number.int({ min: 10, max: 100 }),
        total_sales: faker.finance.amount({ min: 1000, max: 10000 }),
        total_orders: faker.number.int({ min: 10, max: 100 }),
        licenses_activated: faker.number.int({ min: 5, max: 50 }),
        licenses_expired: faker.number.int({ min: 0, max: 10 }),
        total_usage_events: faker.number.int({ min: 1000, max: 5000 }),
        abuse_attempts: faker.number.int({ min: 0, max: 10 }),
      },
      totals: {
        users: faker.number.int({ min: 5000, max: 20000 }),
        paid_users: faker.number.int({ min: 2000, max: 10000 }),
        revenue: faker.finance.amount({ min: 50000, max: 200000 }),
        licenses_activated: faker.number.int({ min: 1000, max: 5000 }),
        abuse_attempts: faker.number.int({ min: 100, max: 500 }),
      },
      last_30_days: {
        active_users: faker.number.int({ min: 1000, max: 5000 }),
        new_users: faker.number.int({ min: 100, max: 500 }),
        revenue: faker.finance.amount({ min: 10000, max: 50000 }),
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
    });
  }),
];
