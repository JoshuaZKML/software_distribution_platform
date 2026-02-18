'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import apiClient from '@/lib/api/client';
import { Button } from '@/components/ui/Button';
import Link from 'next/link';

export default function VerifyEmailPage() {
  const params = useParams();
  const router = useRouter();
  const token = params.token as string;
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const verifyEmail = async () => {
      try {
        await apiClient.get(`/api/v1/auth/verify-email/${token}/`);
        setStatus('success');
        setMessage('Your email has been verified. You can now log in.');
      } catch (err: any) {
        setStatus('error');
        setMessage(err.response?.data?.detail || 'Verification failed. The link may be invalid or expired.');
      }
    };
    verifyEmail();
  }, [token]);

  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <p className="text-foreground">Verifying your email...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8 text-center">
        {status === 'success' ? (
          <>
            <h2 className="text-3xl font-extrabold text-foreground">Email Verified</h2>
            <p className="text-muted-foreground">{message}</p>
            <Button onClick={() => router.push('/login')}>Go to Login</Button>
          </>
        ) : (
          <>
            <h2 className="text-3xl font-extrabold text-foreground">Verification Failed</h2>
            <p className="text-error">{message}</p>
            <Link href="/login">
              <Button variant="outline">Back to Login</Button>
            </Link>
          </>
        )}
      </div>
    </div>
  );
}