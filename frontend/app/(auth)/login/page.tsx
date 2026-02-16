'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAuth } from '@/lib/hooks/useAuth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import FingerprintJS from '@fingerprintjs/fingerprintjs';

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginForm) => {
    try {
      setError(null);
      const fp = await FingerprintJS.load();
      const result = await fp.get();
      const deviceFingerprint = result.visitorId;

      await login({ ...data, device_fingerprint: deviceFingerprint });
      router.push('/');
    } catch (err) {
      setError('Invalid email or password');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-slate-900 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900 dark:text-white">
            Sign in to your account
          </h2>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          <div className="rounded-md shadow-sm -space-y-px">
            <Input
              label="Email address"
              type="email"
              {...register('email')}
              error={errors.email?.message}
              placeholder="Email address"
              className="rounded-t-md rounded-b-none"
            />
            <Input
              label="Password"
              type="password"
              {...register('password')}
              error={errors.password?.message}
              placeholder="Password"
              className="rounded-b-md rounded-t-none"
            />
          </div>

          {error && <div className="text-red-500 text-sm">{error}</div>}

          <div>
            <Button type="submit" disabled={isSubmitting} className="w-full">
              {isSubmitting ? 'Signing in...' : 'Sign in'}
            </Button>
          </div>

          <div className="flex items-center justify-between">
            <div className="text-sm">
              <Link
                href="/forgot-password"
                className="font-medium text-primary-600 hover:text-primary-500"
              >
                Forgot your password?
              </Link>
            </div>
            <div className="text-sm">
              <Link
                href="/register"
                className="font-medium text-primary-600 hover:text-primary-500"
              >
                Sign up
              </Link>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
