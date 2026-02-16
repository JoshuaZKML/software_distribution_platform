import { cn } from '@/lib/utils/cn';

interface CardProps {
  title: string;
  value: string | number;
  className?: string;
}

export function Card({ title, value, className }: CardProps) {
  return (
    <div className={cn('bg-white dark:bg-slate-800 p-4 rounded-lg shadow', className)}>
      <h3 className="text-sm text-gray-500 dark:text-gray-400">{title}</h3>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  );
}
