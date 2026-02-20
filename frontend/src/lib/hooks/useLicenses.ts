import { useV1LicensesMyLicensesList } from '@/lib/api/generated/api';
import type { UseQueryResult } from '@tanstack/react-query';

// Define the expected paginated structure
export interface PaginatedActivationCodeList {
  count: number;
  next?: string | null;
  previous?: string | null;
  results: ActivationCode[];
}

// Define the ActivationCode type locally based on the fields we use
export interface ActivationCode {
  id: string;
  software_name: string;
  software_slug: string;
  human_code: string;
  status: string;
  expires_at?: string;
  // add other fields as needed from the API response
}

/**
 * Custom hook to fetch the current user's licenses.
 * Wraps the generated hook and normalises the data (handles AxiosResponse vs raw data).
 */
export const useMyLicenses = (): UseQueryResult<PaginatedActivationCodeList | undefined, unknown> => {
  return useV1LicensesMyLicensesList(
    {}, // query parameters (none required)
    {
      query: {
        select: (response: unknown): PaginatedActivationCodeList => {
          // If the response is an AxiosResponse-like object, extract its data property.
          // Otherwise, assume it's already the unwrapped data.
          if (
            response &&
            typeof response === 'object' &&
            'data' in response &&
            response.data &&
            typeof response.data === 'object'
          ) {
            return response.data as PaginatedActivationCodeList;
          }
          return response as PaginatedActivationCodeList;
        },
      },
    }
  );
};