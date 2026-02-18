import apiClient from './client';

/**
 * Custom fetcher for Orval-generated hooks.
 * Supports both string URL and config object formats.
 * Unwraps the Axios response so hooks return `response.data`.
 */
export function fetcher<T>(
  urlOrConfig: string | any,
  options?: any
): Promise<T> {
  // Handle both string URL and config object formats
  const config = typeof urlOrConfig === 'string'
    ? { url: urlOrConfig, ...options }
    : { ...urlOrConfig, ...options };

  return apiClient(config).then((response) => response.data);
}