'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useState } from 'react';
import Link from 'next/link';
import { axiosInstance } from '@/lib/api/client';

const forgotSchema = z.object({
  email: z.string().email(),
});

type ForgotForm = z.infer<typeof forgotSchema>;

export default function ForgotPasswordPage() {
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotForm>({
    resolver: zodResolver(forgotSchema),
  });

  const onSubmit = async (data: ForgotForm) => {
    try {
      setError(null);
      await axiosInstance.post('/auth/reset-password/', data);
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Request failed');
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8 text-center">
          <h2 className="text-3xl font-extrabold text-foreground">
            Check your email
          </h2>
          <p className="text-muted-foreground">
            We've sent a password reset link to your email.
          </p>
          <Link href="/login">
            <Button>Back to Login</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-foreground">
            Reset your password
          </h2>
          <p className="mt-2 text-center text-sm text-muted-foreground">
            Enter your email address and we'll send you a link to reset your password.
          </p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          <Input
            label="Email address"
            type="email"
            {...register('email')}
            error={errors.email?.message}
            placeholder="Email address"
          />

          {error && <div className="text-error text-sm">{error}</div>}

          <div>
            <Button type="submit" disabled={isSubmitting} className="w-full">
              {isSubmitting ? 'Sending...' : 'Send reset link'}
            </Button>
          </div>

          <div className="text-sm text-center">
            <Link
              href="/login"
              className="font-medium text-primary hover:text-primary/80"
            >
              Back to login
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}