import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from '@/lib/constants/auth';
import { refreshToken } from './interceptors';

// In‑memory token for better security (reduces XSS exposure)
let memoryAccessToken: string | null = null;

export const setMemoryAccessToken = (token: string | null) => {
  memoryAccessToken = token;
};

const apiClient: AxiosInstance = axios.create({
  baseURL:
    process.env.NEXT_PUBLIC_USE_REAL_API === 'true'
      ? process.env.NEXT_PUBLIC_API_URL
      : '/api/v1',
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor – use memory token first, fallback to localStorage
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (typeof window !== 'undefined') {
    const token = memoryAccessToken ?? localStorage.getItem(ACCESS_TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Response interceptor – handle token refresh with a lock to prevent race conditions
let refreshPromise: Promise<string | null> | null = null;

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      // Use a single refresh promise across all concurrent requests
      if (!refreshPromise) {
        refreshPromise = refreshToken().finally(() => {
          refreshPromise = null;
        });
      }
      const newToken = await refreshPromise;

      if (newToken) {
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      }
    }
    return Promise.reject(error);
  }
);

export { apiClient };
export default apiClient;