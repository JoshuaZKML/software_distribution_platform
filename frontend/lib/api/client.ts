// lib/api/client.ts
import axios from 'axios';

const axiosInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
axiosInstance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for token refresh
axiosInstance.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        const response = await axios.post(
          `${process.env.NEXT_PUBLIC_API_URL}/auth/token/refresh/`,
          { refresh: refreshToken }
        );
        localStorage.setItem('access_token', response.data.access);
        axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${response.data.access}`;
        return axiosInstance(originalRequest);
      } catch (refreshError) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

// For Orval mutator (function that returns data)
export const apiClient = async <T>(url: string, options?: any): Promise<T> => {
  const response = await axiosInstance({ url, ...options });
  return response.data;
};

// For manual use (e.g., in hooks) – export the instance as well
export { axiosInstance };