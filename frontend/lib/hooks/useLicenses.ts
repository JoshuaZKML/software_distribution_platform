import { useV1LicensesMyLicensesList } from '@/lib/api/generated';

export const useMyLicenses = () => {
  return useV1LicensesMyLicensesList({});
};