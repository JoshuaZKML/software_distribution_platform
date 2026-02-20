'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAuth } from '@/lib/hooks/useAuth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

const loginSchema = z.object({
  email: z
    .string()
    .min(1, 'Email is required')
    .email('Please enter a valid email address'),
  password: z
    .string()
    .min(1, 'Password is required')
    .min(8, 'Password must be at least 8 characters'),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [fpPromise, setFpPromise] = useState<Promise<any> | null>(null);

  // Load FingerprintJS only on the client side
  useEffect(() => {
    import('@fingerprintjs/fingerprintjs').then((FingerprintJS) => {
      setFpPromise(FingerprintJS.load());
    });
  }, []);

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
      if (!fpPromise) {
        throw new Error('FingerprintJS is still loading. Please try again.');
      }
      const fp = await fpPromise;
      const result = await fp.get();
      const deviceFingerprint = result.visitorId;

      await login({ ...data, device_fingerprint: deviceFingerprint });
      router.push('/');
    } catch (err: any) {
      console.error('Login error:', err);
      const errorMessage = 
        err.response?.data?.detail || 
        err.response?.data?.message || 
        err.response?.data?.non_field_errors?.[0] ||
        err.message ||
        'Invalid email or password';
      setError(errorMessage);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-foreground">
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

          {error && <div className="text-error text-sm">{error}</div>}

          <div>
            <Button type="submit" disabled={isSubmitting || !fpPromise} className="w-full">
              {isSubmitting ? 'Signing in...' : 'Sign in'}
            </Button>
          </div>

          <div className="flex items-center justify-between">
            <div className="text-sm">
              <Link
                href="/forgot-password"
                className="font-medium text-link hover:text-link/80"
              >
                Forgot your password?
              </Link>
            </div>
            <div className="text-sm">
              <Link
                href="/register"
                className="font-medium text-link hover:text-link/80"
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