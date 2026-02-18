import { useEffect } from 'react';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import apiClient from '@/lib/api/client';
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from '@/lib/constants/auth';
import type { User, LoginRequest } from '@/types/api';

interface AuthState {
  user: User | null;
  isLoading: boolean;
  error: string | null;
  login: (data: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  fetchUser: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

export const useAuth = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isLoading: true,
      error: null,

      login: async (data) => {
        set({ isLoading: true, error: null });
        try {
          // ✅ Now uses relative path without /api/v1
          const response = await apiClient.post('/auth/login', data);
          const { access, refresh, user } = response.data;

          localStorage.setItem(ACCESS_TOKEN_KEY, access);
          localStorage.setItem(REFRESH_TOKEN_KEY, refresh);

          if (user) {
            set({ user, isLoading: false });
          } else {
            await get().fetchUser();
          }
        } catch (error: any) {
          const message = error.response?.data?.detail || 'Login failed';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      logout: async () => {
        try {
          await apiClient.post('/auth/logout');
        } catch {
          // Ignore errors on logout
        } finally {
          localStorage.removeItem(ACCESS_TOKEN_KEY);
          localStorage.removeItem(REFRESH_TOKEN_KEY);
          set({ user: null });
        }
      },

      fetchUser: async () => {
        set({ isLoading: true });
        try {
          const response = await apiClient.get<User>('/auth/users/me');
          set({ user: response.data, isLoading: false, error: null });
        } catch {
          set({ user: null, isLoading: false, error: null });
        }
      },

      refreshUser: async () => {
        await get().fetchUser();
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ user: state.user }),
    }
  )
);

export function useAuthInit() {
  const fetchUser = useAuth((state) => state.fetchUser);
  useEffect(() => {
    fetchUser();
  }, [fetchUser]);
}