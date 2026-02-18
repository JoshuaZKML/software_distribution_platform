'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import apiClient from '@/lib/api/client';

const resetSchema = z.object({
  new_password: z.string().min(8),
  confirm_password: z.string().min(8),
}).refine((data) => data.new_password === data.confirm_password, {
  message: "Passwords don't match",
  path: ["confirm_password"],
});

type ResetForm = z.infer<typeof resetSchema>;

export default function ResetPasswordPage() {
  const params = useParams();
  const token = params.token as string;
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetForm>({
    resolver: zodResolver(resetSchema),
  });

  const onSubmit = async (data: ResetForm) => {
    try {
      setError(null);
      await apiClient.post('/api/v1/auth/reset-password/confirm/', {
        token,
        new_password: data.new_password,
        confirm_password: data.confirm_password,
      });
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Reset failed');
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8 text-center">
          <h2 className="text-3xl font-extrabold text-foreground">
            Password reset successful
          </h2>
          <p className="text-muted-foreground">
            Your password has been reset. You can now log in with your new password.
          </p>
          <Button onClick={() => router.push('/login')}>Go to Login</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-foreground">
            Set new password
          </h2>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          <div className="space-y-4">
            <Input
              label="New password"
              type="password"
              {...register('new_password')}
              error={errors.new_password?.message}
              placeholder="New password"
            />
            <Input
              label="Confirm new password"
              type="password"
              {...register('confirm_password')}
              error={errors.confirm_password?.message}
              placeholder="Confirm new password"
            />
          </div>

          {error && <div className="text-error text-sm">{error}</div>}

          <div>
            <Button type="submit" disabled={isSubmitting} className="w-full">
              {isSubmitting ? 'Resetting...' : 'Reset password'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}