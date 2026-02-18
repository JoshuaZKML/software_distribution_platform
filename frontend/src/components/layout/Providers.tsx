// src/components/layout/Providers.tsx

'use client';

import { Toaster } from 'react-hot-toast';
import { useAuthInit } from '@/lib/hooks/useAuth';
import { useEffect, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { ThemeProvider } from 'next-themes';

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
        try {
          const { worker } = await import('@/mocks/browser');
          await worker.start({
            onUnhandledRequest: 'warn',
          });
        } catch (err) {
          console.error('❌ MSW failed to start:', err);
        }
      }
      setMswReady(true);
    };
    initMsw();
  }, []);

  if (!mswReady) return null;

  return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <QueryClientProvider client={queryClient}>
      <MSWInitializer>
        <AuthInitializer>
          <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
            {mounted ? children : null}
            <Toaster position="top-right" />
          </ThemeProvider>
        </AuthInitializer>
      </MSWInitializer>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}