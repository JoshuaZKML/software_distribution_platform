import { cn } from '@/lib/utils/cn';

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('animate-pulse bg-gray-200 dark:bg-gray-700 rounded', className)}
    />
  );
}
