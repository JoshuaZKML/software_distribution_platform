'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import apiClient from '@/lib/api/client';

const registerSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  password2: z.string().min(8),
  first_name: z.string().min(1),
  last_name: z.string().min(1),
  company: z.string().optional(),
  phone: z.string().optional(),
}).refine((data) => data.password === data.password2, {
  message: "Passwords don't match",
  path: ["password2"],
});

type RegisterForm = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterForm) => {
    try {
      setError(null);
      await apiClient.post('/auth/register/', data);
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed');
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
            We&apos;ve sent a verification link to your email. Please click it to activate your account.
          </p>
          <Link href="/login">
            <Button>Go to Login</Button>
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
            Create an account
          </h2>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          <div className="space-y-4">
            <Input
              label="Email address"
              type="email"
              {...register('email')}
              error={errors.email?.message}
              placeholder="Email address"
            />
            <Input
              label="First name"
              type="text"
              {...register('first_name')}
              error={errors.first_name?.message}
              placeholder="First name"
            />
            <Input
              label="Last name"
              type="text"
              {...register('last_name')}
              error={errors.last_name?.message}
              placeholder="Last name"
            />
            <Input
              label="Company (optional)"
              type="text"
              {...register('company')}
              error={errors.company?.message}
              placeholder="Company"
            />
            <Input
              label="Phone (optional)"
              type="tel"
              {...register('phone')}
              error={errors.phone?.message}
              placeholder="Phone"
            />
            <Input
              label="Password"
              type="password"
              {...register('password')}
              error={errors.password?.message}
              placeholder="Password"
            />
            <Input
              label="Confirm password"
              type="password"
              {...register('password2')}
              error={errors.password2?.message}
              placeholder="Confirm password"
            />
          </div>

          {error && <div className="text-error text-sm">{error}</div>}

          <div>
            <Button type="submit" disabled={isSubmitting} className="w-full">
              {isSubmitting ? 'Creating account...' : 'Sign up'}
            </Button>
          </div>

          <div className="text-sm text-center">
            <Link
              href="/login"
              className="font-medium text-link hover:text-link/80"
            >
              Already have an account? Sign in
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}