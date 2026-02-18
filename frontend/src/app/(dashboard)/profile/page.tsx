'use client';

import { useAuth } from '@/lib/hooks/useAuth';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useState } from 'react';
import apiClient from '@/lib/api/client';

const profileSchema = z.object({
  first_name: z.string().min(1),
  last_name: z.string().min(1),
  company: z.string().optional(),
  phone: z.string().optional(),
});

type ProfileForm = z.infer<typeof profileSchema>;

export default function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      first_name: user?.first_name || '',
      last_name: user?.last_name || '',
      company: user?.company || '',
      phone: user?.phone || '',
    },
  });

  const onSubmit = async (data: ProfileForm) => {
    try {
      setError(null);
      await apiClient.patch(`/api/v1/auth/users/${user?.id}/`, data);
      await refreshUser();
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Update failed');
    }
  };

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-2xl font-bold mb-6">Profile Settings</h1>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          label="Email"
          type="email"
          value={user?.email}
          disabled
          className="bg-gray-100 dark:bg-slate-800"
        />
        <Input
          label="First name"
          {...register('first_name')}
          error={errors.first_name?.message}
        />
        <Input
          label="Last name"
          {...register('last_name')}
          error={errors.last_name?.message}
        />
        <Input
          label="Company"
          {...register('company')}
          error={errors.company?.message}
        />
        <Input
          label="Phone"
          {...register('phone')}
          error={errors.phone?.message}
        />

        {error && <div className="text-state-error text-sm">{error}</div>}
        {success && <div className="text-state-success text-sm">Profile updated successfully</div>}

        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Saving...' : 'Save changes'}
        </Button>
      </form>
    </div>
  );
}