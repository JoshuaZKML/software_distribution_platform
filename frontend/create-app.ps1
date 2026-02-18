# create-app-fixed.ps1
# Run this from the frontend directory

# Ensure directories exist
$folders = @(
    "app\(auth)\login",
    "app\(auth)\register",
    "app\(auth)\forgot-password",
    "app\(auth)\reset-password\[token]",
    "app\(dashboard)\licenses\[id]",
    "app\(dashboard)\profile",
    "components\ui",
    "components\layout",
    "lib\api",
    "lib\hooks",
    "lib\utils",
    "mocks\handlers",
    "types"
)

foreach ($folder in $folders) {
    if (!(Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder -Force | Out-Null
    }
}

# File contents
@"
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from '@/components/layout/Providers';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Software Distribution Platform',
  description: 'Enterprise software licensing and distribution',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
"@ | Out-File -FilePath 'app\layout.tsx' -Encoding utf8

@"
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 255 255 255;
    --foreground: 15 23 42;
    --primary: 59 130 246;
    --primary-foreground: 255 255 255;
  }

  .dark {
    --background: 15 23 42;
    --foreground: 248 250 252;
    --primary: 59 130 246;
    --primary-foreground: 255 255 255;
  }

  body {
    @apply bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-50;
  }
}
"@ | Out-File -FilePath 'app\globals.css' -Encoding utf8

@"
'use client';

import { useAuth } from '@/lib/hooks/useAuth';
import { useDashboardStats } from '@/lib/hooks/useDashboardStats';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { TopBar } from '@/components/layout/TopBar';
import { Sidebar } from '@/components/layout/Sidebar';

export default function DashboardPage() {
  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const { data: stats, isLoading: statsLoading, error } = useDashboardStats();

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
    }
  }, [user, authLoading, router]);

  if (authLoading || statsLoading) {
    return (
      <div className="flex h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <TopBar />
          <main className="p-6">
            <Skeleton className="h-8 w-64 mb-4" />
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-24 rounded-lg" />
              ))}
            </div>
          </main>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <TopBar />
          <main className="p-6">
            <div className="text-red-500">Error loading dashboard</div>
          </main>
        </div>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <TopBar />
        <main className="p-6 overflow-auto">
          <h1 className="text-2xl font-bold mb-4">Dashboard</h1>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Welcome back, {user?.email}
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card title="Total Users" value={stats.totals.users.toLocaleString()} />
            <Card title="Active Users (30d)" value={stats.last_30_days.active_users.toLocaleString()} />
            <Card title="Revenue (30d)" value={`\${stats.last_30_days.revenue}`} />
            <Card title="Licenses Activated" value={stats.totals.licenses_activated.toLocaleString()} />
          </div>

          <div className="mt-8">
            <h2 className="text-xl font-semibold mb-4">Recent Activity</h2>
            <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-4">
              <p className="text-gray-500 dark:text-gray-400">Activity feed coming soon...</p>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
"@ | Out-File -FilePath 'app\page.tsx' -Encoding utf8

@"
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
"@ | Out-File -FilePath 'app\(auth)\login\page.tsx' -Encoding utf8

@"
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
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-slate-900 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8 text-center">
          <h2 className="text-3xl font-extrabold text-gray-900 dark:text-white">
            Check your email
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            We've sent a verification link to your email. Please click it to activate your account.
          </p>
          <Link href="/login">
            <Button>Go to Login</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-slate-900 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900 dark:text-white">
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

          {error && <div className="text-red-500 text-sm">{error}</div>}

          <div>
            <Button type="submit" disabled={isSubmitting} className="w-full">
              {isSubmitting ? 'Creating account...' : 'Sign up'}
            </Button>
          </div>

          <div className="text-sm text-center">
            <Link
              href="/login"
              className="font-medium text-primary-600 hover:text-primary-500"
            >
              Already have an account? Sign in
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
"@ | Out-File -FilePath 'app\(auth)\register\page.tsx' -Encoding utf8

@"
'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useState } from 'react';
import Link from 'next/link';
import apiClient from '@/lib/api/client';

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
      await apiClient.post('/auth/reset-password/', data);
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Request failed');
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-slate-900 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8 text-center">
          <h2 className="text-3xl font-extrabold text-gray-900 dark:text-white">
            Check your email
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
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
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-slate-900 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900 dark:text-white">
            Reset your password
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600 dark:text-gray-400">
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

          {error && <div className="text-red-500 text-sm">{error}</div>}

          <div>
            <Button type="submit" disabled={isSubmitting} className="w-full">
              {isSubmitting ? 'Sending...' : 'Send reset link'}
            </Button>
          </div>

          <div className="text-sm text-center">
            <Link
              href="/login"
              className="font-medium text-primary-600 hover:text-primary-500"
            >
              Back to login
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
"@ | Out-File -FilePath 'app\(auth)\forgot-password\page.tsx' -Encoding utf8

@"
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
      await apiClient.post('/auth/reset-password/confirm/', {
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
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-slate-900 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8 text-center">
          <h2 className="text-3xl font-extrabold text-gray-900 dark:text-white">
            Password reset successful
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Your password has been reset. You can now log in with your new password.
          </p>
          <Button onClick={() => router.push('/login')}>Go to Login</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-slate-900 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900 dark:text-white">
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

          {error && <div className="text-red-500 text-sm">{error}</div>}

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
"@ | Out-File -FilePath 'app\(auth)\reset-password\[token]\page.tsx' -Encoding utf8

@"
'use client';

import { useAuth } from '@/lib/hooks/useAuth';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { Sidebar } from '@/components/layout/Sidebar';
import { TopBar } from '@/components/layout/TopBar';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push('/login');
    }
  }, [user, isLoading, router]);

  if (isLoading) return null;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <TopBar />
        <main className="flex-1 overflow-auto bg-gray-50 dark:bg-slate-900">
          {children}
        </main>
      </div>
    </div>
  );
}
"@ | Out-File -FilePath 'app\(dashboard)\layout.tsx' -Encoding utf8

@"
'use client';

import { useMyLicenses } from '@/lib/hooks/useLicenses';
import { Skeleton } from '@/components/ui/Skeleton';
import { Button } from '@/components/ui/Button';
import Link from 'next/link';

export default function LicensesPage() {
  const { data, isLoading, error } = useMyLicenses();

  if (isLoading) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">My Licenses</h1>
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-32 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">My Licenses</h1>
        <div className="text-red-500">Error loading licenses</div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">My Licenses</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white dark:bg-slate-800 p-4 rounded-lg shadow">
          <p className="text-sm text-gray-500 dark:text-gray-400">Total</p>
          <p className="text-2xl font-bold">{data.summary.total}</p>
        </div>
        <div className="bg-white dark:bg-slate-800 p-4 rounded-lg shadow">
          <p className="text-sm text-gray-500 dark:text-gray-400">Active</p>
          <p className="text-2xl font-bold text-green-600">{data.summary.active}</p>
        </div>
        <div className="bg-white dark:bg-slate-800 p-4 rounded-lg shadow">
          <p className="text-sm text-gray-500 dark:text-gray-400">Expiring Soon</p>
          <p className="text-2xl font-bold text-yellow-600">{data.summary.expiring_soon}</p>
        </div>
      </div>

      <div className="space-y-6">
        {data.licenses_by_software.map((group) => (
          <div key={group.software_slug} className="bg-white dark:bg-slate-800 rounded-lg shadow overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 dark:bg-slate-700 border-b dark:border-slate-600">
              <h2 className="font-semibold text-lg">{group.software_name}</h2>
            </div>
            <div className="divide-y dark:divide-slate-700">
              {group.licenses.map((license) => (
                <div key={license.id} className="p-4 flex items-center justify-between">
                  <div>
                    <p className="font-mono text-sm">{license.human_code}</p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Status: <span className={`font-medium ${
                        license.status === 'ACTIVATED' ? 'text-green-600' :
                        license.status === 'EXPIRED' ? 'text-red-600' :
                        'text-yellow-600'
                      }`}>{license.status}</span>
                      {' · '}Expires: {license.expires_at ? new Date(license.expires_at).toLocaleDateString() : 'Never'}
                    </p>
                  </div>
                  <div className="space-x-2">
                    <Link href={`/licenses/${license.id}`}>
                      <Button variant="outline" size="sm">View</Button>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
"@ | Out-File -FilePath 'app\(dashboard)\licenses\page.tsx' -Encoding utf8

@"
'use client';

import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api/client';
import { Skeleton } from '@/components/ui/Skeleton';
import { Button } from '@/components/ui/Button';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import Link from 'next/link';

export default function LicenseDetailPage() {
  const { id } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ['license', id],
    queryFn: async () => {
      const { data } = await apiClient.get(`/licenses/activation-codes/${id}/`);
      return data;
    },
  });

  if (isLoading) {
    return (
      <div className="p-6">
        <Skeleton className="h-8 w-48 mb-4" />
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="text-red-500">Error loading license</div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <Link href="/licenses" className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 mb-4">
        <ArrowLeftIcon className="h-4 w-4 mr-1" />
        Back to licenses
      </Link>
      <h1 className="text-2xl font-bold mb-4">License Details</h1>
      <pre className="bg-gray-100 dark:bg-slate-800 p-4 rounded-lg overflow-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
"@ | Out-File -FilePath 'app\(dashboard)\licenses\[id]\page.tsx' -Encoding utf8

@"
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
      await apiClient.patch(`/auth/users/${user?.id}/`, data);
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

        {error && <div className="text-red-500 text-sm">{error}</div>}
        {success && <div className="text-green-500 text-sm">Profile updated successfully</div>}

        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Saving...' : 'Save changes'}
        </Button>
      </form>
    </div>
  );
}
"@ | Out-File -FilePath 'app\(dashboard)\profile\page.tsx' -Encoding utf8

# --- UI Components ---
@"
import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils/cn';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none',
  {
    variants: {
      variant: {
        default: 'bg-primary-600 text-white hover:bg-primary-700',
        destructive: 'bg-red-500 text-white hover:bg-red-600',
        outline:
          'border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800',
        secondary: 'bg-gray-100 text-gray-900 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-100 dark:hover:bg-gray-700',
        ghost: 'hover:bg-gray-100 dark:hover:bg-gray-800',
        link: 'underline-offset-4 hover:underline text-primary-600',
      },
      size: {
        default: 'h-10 py-2 px-4',
        sm: 'h-9 px-3',
        lg: 'h-11 px-8',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = 'Button';

export { Button, buttonVariants };
"@ | Out-File -FilePath 'components\ui\Button.tsx' -Encoding utf8

@"
import * as React from 'react';
import { cn } from '@/lib/utils/cn';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, label, error, id, ...props }, ref) => {
    const inputId = id || `input-\${Math.random().toString(36).substr(2, 9)}`;
    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
          >
            {label}
          </label>
        )}
        <input
          id={inputId}
          type={type}
          className={cn(
            'flex h-10 w-full rounded-md border border-gray-300 bg-transparent px-3 py-2 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:text-gray-50',
            error && 'border-red-500 focus:ring-red-500',
            className
          )}
          ref={ref}
          {...props}
        />
        {error && <p className="mt-1 text-sm text-red-500">{error}</p>}
      </div>
    );
  }
);
Input.displayName = 'Input';

export { Input };
"@ | Out-File -FilePath 'components\ui\Input.tsx' -Encoding utf8

@"
import { cn } from '@/lib/utils/cn';

interface CardProps {
  title: string;
  value: string | number;
  className?: string;
}

export function Card({ title, value, className }: CardProps) {
  return (
    <div className={cn('bg-white dark:bg-slate-800 p-4 rounded-lg shadow', className)}>
      <h3 className="text-sm text-gray-500 dark:text-gray-400">{title}</h3>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  );
}
"@ | Out-File -FilePath 'components\ui\Card.tsx' -Encoding utf8

@"
import { cn } from '@/lib/utils/cn';

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('animate-pulse bg-gray-200 dark:bg-gray-700 rounded', className)}
    />
  );
}
"@ | Out-File -FilePath 'components\ui\Skeleton.tsx' -Encoding utf8

# --- Layout Components ---
@"
'use client';

import { Toaster } from 'react-hot-toast';
import { useAuthInit } from '@/lib/hooks/useAuth';
import { useEffect, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 10 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AuthInitializer({ children }: { children: React.ReactNode }) {
  useAuthInit();
  return <>{children}</>;
}

function MSWInitializer({ children }: { children: React.ReactNode }) {
  const [mswReady, setMswReady] = useState(false);

  useEffect(() => {
    const initMsw = async () => {
      if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_USE_REAL_API !== 'true') {
        const { worker } = await import('@/mocks/browser');
        await worker.start({
          onUnhandledRequest: 'bypass',
        });
      }
      setMswReady(true);
    };
    initMsw();
  }, []);

  if (!mswReady) return null;

  return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <MSWInitializer>
        <AuthInitializer>
          {children}
          <Toaster position="top-right" />
        </AuthInitializer>
      </MSWInitializer>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
"@ | Out-File -FilePath 'components\layout\Providers.tsx' -Encoding utf8

@"
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils/cn';
import {
  HomeIcon,
  KeyIcon,
  CreditCardIcon,
  DocumentTextIcon,
  BellIcon,
  UserIcon,
  Cog6ToothIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';
import { useAuth } from '@/lib/hooks/useAuth';

const navigation = [
  { name: 'Dashboard', href: '/', icon: HomeIcon, roles: ['USER', 'ADMIN', 'SUPER_ADMIN'] },
  { name: 'Licenses', href: '/licenses', icon: KeyIcon, roles: ['USER', 'ADMIN', 'SUPER_ADMIN'] },
  { name: 'Subscriptions', href: '/subscriptions', icon: CreditCardIcon, roles: ['USER', 'ADMIN', 'SUPER_ADMIN'] },
  { name: 'Invoices', href: '/invoices', icon: DocumentTextIcon, roles: ['USER', 'ADMIN', 'SUPER_ADMIN'] },
  { name: 'Notifications', href: '/notifications', icon: BellIcon, roles: ['USER', 'ADMIN', 'SUPER_ADMIN'] },
  { name: 'Profile', href: '/profile', icon: UserIcon, roles: ['USER', 'ADMIN', 'SUPER_ADMIN'] },
  { name: 'Security', href: '/security', icon: ShieldCheckIcon, roles: ['ADMIN', 'SUPER_ADMIN'] },
  { name: 'Settings', href: '/settings', icon: Cog6ToothIcon, roles: ['SUPER_ADMIN'] },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const role = user?.role || 'USER';

  const filteredNav = navigation.filter(item => item.roles.includes(role));

  return (
    <nav className="w-64 bg-white dark:bg-slate-800 border-r dark:border-slate-700 flex flex-col">
      <div className="p-4 border-b dark:border-slate-700">
        <h1 className="text-xl font-bold text-primary-600">Software Distro</h1>
      </div>
      <div className="flex-1 p-4 space-y-1">
        {filteredNav.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/50 dark:text-primary-300'
                  : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-slate-700'
              )}
            >
              <item.icon className="h-5 w-5 mr-3" />
              {item.name}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
"@ | Out-File -FilePath 'components\layout\SideNav.tsx' -Encoding utf8

@"
'use client';

import { useAuth } from '@/lib/hooks/useAuth';
import { BellIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import { Button } from '@/components/ui/Button';
import { useRouter } from 'next/navigation';
import { useWebSocket } from '@/lib/hooks/useWebSocket';
import { useEffect, useState } from 'react';

export function TopBar() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const { lastMessage } = useWebSocket();
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    if (lastMessage) {
      setUnreadCount(prev => prev + 1);
    }
  }, [lastMessage]);

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  return (
    <header className="bg-white dark:bg-slate-800 border-b dark:border-slate-700 h-16 flex items-center px-6">
      <div className="flex-1 flex items-center">
        <div className="relative w-96">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search..."
            className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
      </div>
      <div className="flex items-center space-x-4">
        <button className="relative p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
          <BellIcon className="h-6 w-6" />
          {unreadCount > 0 && (
            <span className="absolute top-1 right-1 inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-white transform translate-x-1/2 -translate-y-1/2 bg-red-500 rounded-full">
              {unreadCount}
            </span>
          )}
        </button>
        <div className="flex items-center space-x-3">
          <div className="text-sm text-right">
            <p className="font-medium">{user?.first_name} {user?.last_name}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">{user?.role}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            Logout
          </Button>
        </div>
      </div>
    </header>
  );
}
"@ | Out-File -FilePath 'components\layout\TopBar.tsx' -Encoding utf8

# --- Lib Utils ---
@"
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
"@ | Out-File -FilePath 'lib\utils\cn.ts' -Encoding utf8

# --- Hooks ---
@"
import { useEffect } from 'react';
import { create } from 'zustand';
import apiClient from '@/lib/api/client';
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
      const response = await apiClient.post('/auth/login/', data);
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
      const response = await apiClient.get('/auth/users/me/');
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
"@ | Out-File -FilePath 'lib\hooks\useAuth.ts' -Encoding utf8

@"
import { useEffect, useRef, useState } from 'react';
import { useAuth } from './useAuth';

interface WebSocketMessage {
  type: string;
  data: any;
}

export function useWebSocket() {
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [readyState, setReadyState] = useState<number>(WebSocket.CONNECTING);
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<NodeJS.Timeout>();
  const { user } = useAuth();

  useEffect(() => {
    if (!user) return;

    const connect = () => {
      const url = process.env.NEXT_PUBLIC_WS_URL;
      if (!url) return;

      ws.current = new WebSocket(url);

      ws.current.onopen = () => {
        setReadyState(WebSocket.OPEN);
        ws.current?.send(JSON.stringify({ type: 'auth', token: localStorage.getItem('access_token') }));
      };

      ws.current.onclose = () => {
        setReadyState(WebSocket.CLOSED);
        reconnectTimeout.current = setTimeout(connect, 5000);
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error', error);
      };

      ws.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          setLastMessage(message);
        } catch (e) {
          console.error('Failed to parse WebSocket message', e);
        }
      };
    };

    connect();

    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (ws.current) ws.current.close();
    };
  }, [user]);

  const sendMessage = (message: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    }
  };

  return { lastMessage, readyState, sendMessage };
}
"@ | Out-File -FilePath 'lib\hooks\useWebSocket.ts' -Encoding utf8

@"
import { useMyLicenses as useGeneratedMyLicenses } from '@/lib/api/generated';

export const useMyLicenses = () => {
  return useGeneratedMyLicenses();
};
"@ | Out-File -FilePath 'lib\hooks\useLicenses.ts' -Encoding utf8

@"
import { useDashboardStats as useGeneratedDashboardStats } from '@/lib/api/generated';

export const useDashboardStats = () => {
  return useGeneratedDashboardStats();
};
"@ | Out-File -FilePath 'lib\hooks\useDashboardStats.ts' -Encoding utf8

@"
import toast from 'react-hot-toast';

export const useToast = () => {
  return {
    success: (message: string) => toast.success(message),
    error: (message: string) => toast.error(message),
    info: (message: string) => toast(message),
  };
};
"@ | Out-File -FilePath 'lib\hooks\useToast.ts' -Encoding utf8

# --- Mocks ---
@"
import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

export const worker = setupWorker(...handlers);
"@ | Out-File -FilePath 'mocks\browser.ts' -Encoding utf8

@"
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);
"@ | Out-File -FilePath 'mocks\server.ts' -Encoding utf8

@"
import { authHandlers } from './auth';
import { licensesHandlers } from './licenses';
import { dashboardHandlers } from './dashboard';

export const handlers = [...authHandlers, ...licensesHandlers, ...dashboardHandlers];
"@ | Out-File -FilePath 'mocks\handlers\index.ts' -Encoding utf8

@"
import { http, HttpResponse } from 'msw';
import { faker } from '@faker-js/faker';

const mockUser = {
  id: faker.string.uuid(),
  email: 'admin@example.com',
  first_name: 'Admin',
  last_name: 'User',
  role: 'ADMIN' as const,
  company: 'Acme Inc',
  phone: '+1234567890',
  is_active: true,
  date_joined: new Date().toISOString(),
  last_login: new Date().toISOString(),
};

export const authHandlers = [
  http.post('/api/v1/auth/login/', async ({ request }) => {
    const { email, password } = await request.json() as any;
    if (email === 'admin@example.com' && password === 'password') {
      return HttpResponse.json({
        refresh: faker.string.uuid(),
        access: faker.string.uuid(),
        user: mockUser,
      });
    }
    return new HttpResponse(null, { status: 401, statusText: 'Invalid credentials' });
  }),

  http.post('/api/v1/auth/token/refresh/', () => {
    return HttpResponse.json({
      access: faker.string.uuid(),
    });
  }),

  http.get('/api/v1/auth/users/me/', () => {
    return HttpResponse.json(mockUser);
  }),

  http.post('/api/v1/auth/register/', async ({ request }) => {
    return HttpResponse.json({
      id: faker.string.uuid(),
      email: 'newuser@example.com',
      role: 'USER',
      message: 'Registration successful. Please verify your email.',
    });
  }),

  http.post('/api/v1/auth/reset-password/', () => {
    return HttpResponse.json({ detail: 'Password reset email sent.' });
  }),

  http.post('/api/v1/auth/reset-password/confirm/', () => {
    return HttpResponse.json({ detail: 'Password reset successful.' });
  }),
];
"@ | Out-File -FilePath 'mocks\handlers\auth.ts' -Encoding utf8

@"
import { http, HttpResponse } from 'msw';
import { faker } from '@faker-js/faker';

const generateLicense = () => ({
  id: faker.string.uuid(),
  software_name: faker.company.name() + ' Software',
  software_slug: faker.helpers.slugify(faker.company.name()).toLowerCase(),
  human_code: faker.string.alphanumeric(25).toUpperCase().match(/.{5}/g)?.join('-') || '',
  license_type: faker.helpers.arrayElement(['TRIAL', 'STANDARD', 'PREMIUM', 'ENTERPRISE', 'LIFETIME']),
  status: faker.helpers.arrayElement(['ACTIVATED', 'INACTIVE', 'EXPIRED']),
  user_email: faker.internet.email(),
  max_activations: 5,
  activation_count: faker.number.int({ min: 0, max: 5 }),
  expires_at: faker.date.future().toISOString(),
  is_valid: true,
  remaining_activations: faker.number.int({ min: 0, max: 5 }),
  device_fingerprint: faker.string.alphanumeric(32),
  device_name: faker.helpers.arrayElement(['Windows PC', 'MacBook Pro', 'Linux Workstation']),
});

export const licensesHandlers = [
  http.get('/api/v1/licenses/my-licenses/', () => {
    return HttpResponse.json({
      summary: {
        total: 10,
        active: 7,
        expiring_soon: 2,
      },
      licenses_by_software: [
        {
          software_name: 'Product A',
          software_slug: 'product-a',
          licenses: faker.helpers.multiple(generateLicense, { count: 3 }),
        },
        {
          software_name: 'Product B',
          software_slug: 'product-b',
          licenses: faker.helpers.multiple(generateLicense, { count: 2 }),
        },
      ],
    });
  }),

  http.get('/api/v1/licenses/activation-codes/:id/', ({ params }) => {
    return HttpResponse.json(generateLicense());
  }),
];
"@ | Out-File -FilePath 'mocks\handlers\licenses.ts' -Encoding utf8

@"
import { http, HttpResponse } from 'msw';
import { faker } from '@faker-js/faker';

export const dashboardHandlers = [
  http.get('/api/v1/dashboard/stats/', () => {
    return HttpResponse.json({
      latest_daily: {
        date: faker.date.recent().toISOString().split('T')[0],
        total_users: faker.number.int({ min: 1000, max: 5000 }),
        active_users: faker.number.int({ min: 500, max: 3000 }),
        new_users: faker.number.int({ min: 10, max: 100 }),
        total_sales: faker.finance.amount({ min: 1000, max: 10000 }),
        total_orders: faker.number.int({ min: 10, max: 100 }),
        licenses_activated: faker.number.int({ min: 5, max: 50 }),
        licenses_expired: faker.number.int({ min: 0, max: 10 }),
        total_usage_events: faker.number.int({ min: 1000, max: 5000 }),
        abuse_attempts: faker.number.int({ min: 0, max: 10 }),
      },
      totals: {
        users: faker.number.int({ min: 5000, max: 20000 }),
        paid_users: faker.number.int({ min: 2000, max: 10000 }),
        revenue: faker.finance.amount({ min: 50000, max: 200000 }),
        licenses_activated: faker.number.int({ min: 1000, max: 5000 }),
        abuse_attempts: faker.number.int({ min: 100, max: 500 }),
      },
      last_30_days: {
        active_users: faker.number.int({ min: 1000, max: 5000 }),
        new_users: faker.number.int({ min: 100, max: 500 }),
        revenue: faker.finance.amount({ min: 10000, max: 50000 }),
      },
      cohorts: [
        {
          cohort_date: '2026-01-01',
          period: 'week',
          period_number: 1,
          retention_rate: 60.0,
        },
        {
          cohort_date: '2026-01-01',
          period: 'week',
          period_number: 2,
          retention_rate: 45.0,
        },
      ],
      snapshot_time: new Date().toISOString(),
    });
  }),
];
"@ | Out-File -FilePath 'mocks\handlers\dashboard.ts' -Encoding utf8

Write-Host "All frontend files created successfully!" -ForegroundColor Green