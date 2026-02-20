import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from '@/lib/constants/auth';
import apiClient, { setMemoryAccessToken } from './client';

export async function refreshToken(): Promise<string | null> {
  const refresh = localStorage.getItem(REFRESH_TOKEN_KEY);
  if (!refresh) return null;

  try {
    // Fixed path: no extra /api/v1 (baseURL already includes it)
    const response = await apiClient.post('/auth/token/refresh/', { refresh });
    const { access } = response.data;

    localStorage.setItem(ACCESS_TOKEN_KEY, access);
    setMemoryAccessToken(access); // update in‑memory copy
    return access;
  } catch {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    setMemoryAccessToken(null);
    // Optional: force redirect on refresh failure (commented for now)
    // window.location.href = '/login';
    return null;
  }
}