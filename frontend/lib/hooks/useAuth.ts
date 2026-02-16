import { useEffect } from 'react';
import { create } from 'zustand';
import { axiosInstance } from '@/lib/api/client';  // ← changed import
import type { User, LoginRequest } from '@/lib/api/types';

interface AuthState {
  user: User | null;
  isLoading: boolean;
  error: string | null;
  login: (data: LoginRequest) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  isLoading: true,
  error: null,
  login: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const response = await axiosInstance.post('/auth/login/', data);  // ← use axiosInstance
      const { access, refresh, user } = response.data;
      localStorage.setItem('access_token', access);
      localStorage.setItem('refresh_token', refresh);
      set({ user, isLoading: false });
    } catch (error: any) {
      set({ error: error.response?.data?.detail || 'Login failed', isLoading: false });
      throw error;
    }
  },
  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    set({ user: null });
  },
  refreshUser: async () => {
    set({ isLoading: true });
    try {
      const response = await axiosInstance.get('/auth/users/me/');  // ← use axiosInstance
      set({ user: response.data, isLoading: false });
    } catch {
      set({ user: null, isLoading: false });
    }
  },
}));

export function useAuthInit() {
  const refreshUser = useAuth((state) => state.refreshUser);
  useEffect(() => {
    refreshUser();
  }, [refreshUser]);
}