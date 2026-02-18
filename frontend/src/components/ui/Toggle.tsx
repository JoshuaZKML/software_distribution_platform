import * as React from 'react';
import { cn } from '@/lib/utils/cn';

interface ToggleProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export const Toggle = React.forwardRef<HTMLInputElement, ToggleProps>(
  ({ className, label, id, ...props }, ref) => {
    const generatedId = React.useId();
    const toggleId = id || generatedId;

    return (
      <div className="flex items-center">
        <input
          type="checkbox"
          id={toggleId}
          className="sr-only"
          ref={ref}
          {...props}
        />
        <label
          htmlFor={toggleId}
          className={cn(
            'relative inline-flex h-6 w-11 cursor-pointer rounded-full transition-colors duration-fast',
            props.checked ? 'bg-action-primary' : 'bg-state-disabled',
            className
          )}
        >
          <span
            className={cn(
              'inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform duration-fast',
              props.checked ? 'translate-x-6' : 'translate-x-1'
            )}
          />
        </label>
        {label && (
          <label htmlFor={toggleId} className="ml-3 text-sm text-text-main cursor-pointer">
            {label}
          </label>
        )}
      </div>
    );
  }
);
Toggle.displayName = 'Toggle';