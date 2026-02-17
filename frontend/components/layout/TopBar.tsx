'use client';

import { useAuth } from '@/lib/hooks/useAuth';
import { BellIcon, MagnifyingGlassIcon, SunIcon, MoonIcon } from '@heroicons/react/24/outline';
import { Button } from '@/components/ui/Button';
import { useRouter } from 'next/navigation';
import { useWebSocket } from '@/lib/hooks/useWebSocket';
import { useEffect, useState } from 'react';

export function TopBar() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const { lastMessage } = useWebSocket();
  const [unreadCount, setUnreadCount] = useState(0);
  const [isDark, setIsDark] = useState(false);

  // --- Theme handling ---
  useEffect(() => {
    // Check localStorage first, then system preference
    const storedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initialDark = storedTheme === 'dark' || (!storedTheme && prefersDark);

    if (initialDark) {
      document.documentElement.classList.add('dark');
      setIsDark(true);
    } else {
      document.documentElement.classList.remove('dark');
      setIsDark(false);
    }
  }, []);

  const toggleTheme = () => {
    const html = document.documentElement;
    if (html.classList.contains('dark')) {
      html.classList.remove('dark');
      localStorage.setItem('theme', 'light');
      setIsDark(false);
    } else {
      html.classList.add('dark');
      localStorage.setItem('theme', 'dark');
      setIsDark(true);
    }
  };
  // ----------------------

  // --- Notification badge ---
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
    <header className="bg-white dark:bg-slate-800 border-b dark:border-slate-700 h-16 flex items-center px-4 sm:px-6">
      <div className="flex-1 flex items-center">
        {/* Search – hidden on very small screens, visible on sm+ */}
        <div className="hidden sm:block relative w-96">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search..."
            className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        {/* Mobile search icon (optional) – you could add a pop‑up search later */}
      </div>

      <div className="flex items-center space-x-2 sm:space-x-4">
        {/* Theme toggle button */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-md text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
          aria-label="Toggle theme"
        >
          {isDark ? (
            <SunIcon className="h-6 w-6" />
          ) : (
            <MoonIcon className="h-6 w-6" />
          )}
        </button>

        {/* Notifications */}
        <button className="relative p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
          <BellIcon className="h-6 w-6" />
          {unreadCount > 0 && (
            <span className="absolute top-1 right-1 inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-white transform translate-x-1/2 -translate-y-1/2 bg-red-500 rounded-full">
              {unreadCount}
            </span>
          )}
        </button>

        {/* User info & logout */}
        <div className="flex items-center space-x-3">
          <div className="hidden sm:block text-sm text-right">
            <p className="font-medium text-gray-900 dark:text-white">
              {user?.first_name} {user?.last_name}
            </p>
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