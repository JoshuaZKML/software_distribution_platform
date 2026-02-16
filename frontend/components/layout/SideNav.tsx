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

export function SideNav() {
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
