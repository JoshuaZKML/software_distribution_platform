// src/lib/hooks/useSoftware.ts

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api/client';  // default import
import type { Software, SoftwareRequest } from '@/types/api';

export const useSoftwareList = (params?: any) => {
  return useQuery({
    queryKey: ['software', params],
    queryFn: async () => {
      const response = await apiClient.get('/products/software/', { params });
      return response.data;
    },
  });
};

export const useSoftwareRetrieve = (slug: string) => {
  return useQuery({
    queryKey: ['software', slug],
    queryFn: async () => {
      const response = await apiClient.get(`/products/software/${slug}/`);
      return response.data;
    },
    enabled: !!slug,
  });
};

export const useCreateSoftware = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: SoftwareRequest) => apiClient.post('/products/software/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['software'] });
    },
  });
};

export const useUpdateSoftware = (slug: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: SoftwareRequest) => apiClient.patch(`/products/software/${slug}/`, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['software'] });
      queryClient.invalidateQueries({ queryKey: ['software', slug] });
    },
  });
};

export const useDeleteSoftware = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => apiClient.delete(`/products/software/${slug}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['software'] });
    },
  });
};

export const useToggleSoftwareActive = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => apiClient.post(`/products/software/${slug}/toggle_active/`),
    onSuccess: (_, slug) => {
      queryClient.invalidateQueries({ queryKey: ['software'] });
      queryClient.invalidateQueries({ queryKey: ['software', slug] });
    },
  });
};