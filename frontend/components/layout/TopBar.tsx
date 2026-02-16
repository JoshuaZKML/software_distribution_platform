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
