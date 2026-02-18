import { useV1LicensesMyLicensesList } from '@/lib/api/generated';
import type { UseQueryResult } from '@tanstack/react-query';
import type { ActivationCode } from '@/lib/api/generated';
import { useMemo } from 'react';

export interface PaginatedActivationCodeList {
  count: number;
  next?: string | null;
  previous?: string | null;
 results: ActivationCode[];
}

// Wraps the generated hook and ensures proper typing
export const useMyLicenses = (): UseQueryResult<PaginatedActivationCodeList, unknown> => {
  // Call the generated hook without explicit typing to avoid DataTag issues
  const result = useV1LicensesMyLicensesList({}) as any;
  
  // Ensure the data is properly unwrapped
  const processedResult = useMemo(() => {
    if (!result.data) return result;
    
    // If data is AxiosResponse, extract the data property
    if (result.data && typeof result.data === 'object' && 'data' in result.data) {
      return {
        ...result,
        data: result.data.data as PaginatedActivationCodeList
      };
    }
    
    // Otherwise assume it's already unwrapped
    return result;
  }, [result.data]);
  
  return processedResult as UseQueryResult<PaginatedActivationCodeList, unknown>;
};
