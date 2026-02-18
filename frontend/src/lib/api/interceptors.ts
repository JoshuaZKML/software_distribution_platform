import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from '@/lib/constants/auth';
import apiClient from './client';

export async function refreshToken(): Promise<string | null> {
  const refresh = localStorage.getItem(REFRESH_TOKEN_KEY);
  if (!refresh) return null;

  try {
    const response = await apiClient.post('/auth/token/refresh/', { refresh });
    const { access } = response.data;
    localStorage.setItem(ACCESS_TOKEN_KEY, access);
    return access;
  } catch {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    return null;
  }
}