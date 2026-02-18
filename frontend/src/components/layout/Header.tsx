'use client';

import { useAuth } from '@/lib/hooks/useAuth';
import { useTheme } from 'next-themes';
import { Button } from '@/components/ui/Button';
import { Moon, Sun, LogOut } from 'lucide-react';

export function Header() {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Logout failed', error);
    }
  };

  return (
    <header className="border-b border-border-subtle bg-background-surface px-6 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <h2 className="text-lg font-semibold text-text-main">Dashboard</h2>
        </div>
        <div className="flex items-center space-x-4">
          <span className="text-sm text-text-muted">
            {user?.first_name} {user?.last_name}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </Button>
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            <LogOut size={18} />
          </Button>
        </div>
      </div>
    </header>
  );
}