'use client';

import { useAuth } from '@/lib/hooks/useAuth';
import { BellIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import { Button } from '@/components/ui/Button';
import { useRouter } from 'next/navigation';
import { useWebSocket } from '@/lib/hooks/useWebSocket';
import { useEffect, useState } from 'react';
import { useTheme } from 'next-themes';
import { SunIcon, MoonIcon } from '@heroicons/react/24/outline';

export function TopBar() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const { lastMessage } = useWebSocket();
  const [unreadCount, setUnreadCount] = useState(0);
  const { theme, setTheme } = useTheme();

  // Notification badge update
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
    <header className="bg-background-surface border-b border-border-subtle h-16 flex items-center px-4 sm:px-6">
      <div className="flex-1 flex items-center">
        <div className="hidden sm:block relative w-96">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-text-muted" />
          <input
            type="text"
            placeholder="Search..."
            className="w-full pl-10 pr-4 py-2 border border-border-subtle rounded-lg bg-background-secondary text-text-main placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-action-primary"
          />
        </div>
      </div>

      <div className="flex items-center space-x-2 sm:space-x-4">
        <button
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          className="p-2 rounded-md text-text-muted hover:text-text-main focus:outline-none focus:ring-2 focus:ring-action-primary"
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? (
            <SunIcon className="h-6 w-6" />
          ) : (
            <MoonIcon className="h-6 w-6" />
          )}
        </button>

        <button className="relative p-2 text-text-muted hover:text-text-main focus:outline-none focus:ring-2 focus:ring-action-primary rounded-md">
          <BellIcon className="h-6 w-6" />
          {unreadCount > 0 && (
            <span className="absolute top-1 right-1 inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-white bg-state-error rounded-full">
              {unreadCount}
            </span>
          )}
        </button>

        <div className="flex items-center space-x-3">
          <div className="hidden sm:block text-sm text-right">
            <p className="font-medium text-text-main">
              {user?.first_name} {user?.last_name}
            </p>
            <p className="text-xs text-text-muted">{user?.role}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            Logout
          </Button>
        </div>
      </div>
    </header>
  );
}