import * as React from 'react';
import { cn } from '@/lib/utils/cn';

export interface StatusBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'success' | 'warning' | 'error' | 'neutral';
}

const StatusBadge = React.forwardRef<HTMLSpanElement, StatusBadgeProps>(
  ({ className, variant = 'neutral', children, ...props }, ref) => {
    return (
      <span
        ref={ref}
        className={cn(
          'inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium uppercase',
          {
            'bg-state-success/10 text-state-success': variant === 'success',
            'bg-state-warning/10 text-state-warning': variant === 'warning',
            'bg-state-error/10 text-state-error': variant === 'error',
            'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200': variant === 'neutral',
          },
          className
        )}
        {...props}
      >
        {children}
      </span>
    );
  }
);
StatusBadge.displayName = 'StatusBadge';

export { StatusBadge };