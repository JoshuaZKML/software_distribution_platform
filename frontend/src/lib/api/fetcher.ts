// src/lib/api/fetcher.ts
import { apiClient } from './client';

export const fetcher = <T>(config: Parameters<typeof apiClient>[0]): Promise<T> => {
  return apiClient(config).then(res => res.data);
};