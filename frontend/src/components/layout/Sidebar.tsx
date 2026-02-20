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
  ComputerDesktopIcon,
  TicketIcon,
  ChartBarIcon,
  UserGroupIcon,
  ClipboardDocumentListIcon,
  ChatBubbleLeftRightIcon,
} from '@heroicons/react/24/outline';
import { useAuth } from '@/lib/hooks/useAuth';

const navigation = [
  // Dashboard
  { name: 'Dashboard', href: '/', icon: HomeIcon, roles: ['USER', 'ADMIN', 'SUPER_ADMIN'] },
  // Software (admin only)
  { name: 'Software', href: '/software', icon: ComputerDesktopIcon, roles: ['ADMIN', 'SUPER_ADMIN'] },
  // Licenses
  { name: 'Licenses', href: '/licenses', icon: KeyIcon, roles: ['USER', 'ADMIN', 'SUPER_ADMIN'] },
  // Payments group
  { name: 'Subscriptions', href: '/subscriptions', icon: CreditCardIcon, roles: ['USER', 'ADMIN', 'SUPER_ADMIN'] },
  { name: 'Invoices', href: '/invoices', icon: DocumentTextIcon, roles: ['USER', 'ADMIN', 'SUPER_ADMIN'] },
  // Tickets (support)
  { name: 'Tickets', href: '/tickets', icon: TicketIcon, roles: ['USER', 'ADMIN', 'SUPER_ADMIN'] },
  // Live Chat (admin only)
  { name: 'Live Chat', href: '/dashboard/chats', icon: ChatBubbleLeftRightIcon, roles: ['ADMIN', 'SUPER_ADMIN'] },
  // Analytics (admin+)
  { name: 'Analytics', href: '/analytics', icon: ChartBarIcon, roles: ['ADMIN', 'SUPER_ADMIN'] },
  // Notifications
  { name: 'Notifications', href: '/notifications', icon: BellIcon, roles: ['USER', 'ADMIN', 'SUPER_ADMIN'] },
  // Profile
  { name: 'Profile', href: '/profile', icon: UserIcon, roles: ['USER', 'ADMIN', 'SUPER_ADMIN'] },
  // Security (admin+)
  { name: 'Security', href: '/security', icon: ShieldCheckIcon, roles: ['ADMIN', 'SUPER_ADMIN'] },
  // Users (admin+)
  { name: 'Users', href: '/users', icon: UserGroupIcon, roles: ['ADMIN', 'SUPER_ADMIN'] },
  // Admin Logs (super_admin only)
  { name: 'Admin Logs', href: '/admin-logs', icon: ClipboardDocumentListIcon, roles: ['SUPER_ADMIN'] },
  // Settings (super_admin only)
  { name: 'Settings', href: '/settings', icon: Cog6ToothIcon, roles: ['SUPER_ADMIN'] },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const role = user?.role || 'USER';

  const filteredNav = navigation.filter(item => item.roles.includes(role));

  return (
    <nav className="w-64 bg-background-surface border-r border-border-subtle flex flex-col">
      <div className="p-4 border-b border-border-subtle">
        <h1 className="text-xl font-bold text-link">Software Distro</h1>
      </div>
      <div className="flex-1 p-4 space-y-1">
        {filteredNav.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors duration-fast',
                isActive
                  ? 'bg-action-primary/10 text-action-primary'
                  : 'text-text-muted hover:bg-background-secondary hover:text-text-main'
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