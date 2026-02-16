import React, { forwardRef } from 'react';
import './Button.css';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  fullWidth?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  as?: 'button' | 'a' | 'span';
  href?: string;
  children: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      loading = false,
      fullWidth = false,
      leftIcon,
      rightIcon,
      as: Component = 'button',
      href,
      children,
      className = '',
      disabled,
      type = 'button',
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || loading;
    const baseClass = 'btn';
    const variantClass = `btn-${variant}`;
    const sizeClass = `btn-${size}`;
    const widthClass = fullWidth ? 'btn-full-width' : '';
    const loadingClass = loading ? 'btn-loading' : '';

    const content = (
      <>
        {loading && <span className="btn-spinner" aria-hidden="true" />}
        {leftIcon && !loading && <span className="btn-icon-left" aria-hidden="true">{leftIcon}</span>}
        <span className={loading ? 'btn-content-loading' : ''}>{children}</span>
        {rightIcon && !loading && <span className="btn-icon-right" aria-hidden="true">{rightIcon}</span>}
      </>
    );

    if (Component === 'a' && href) {
      return (
        <a
          href={href}
          className={`${baseClass} ${variantClass} ${sizeClass} ${widthClass} ${loadingClass} ${className}`}
          aria-disabled={isDisabled}
          tabIndex={isDisabled ? -1 : undefined}
          {...(props as React.AnchorHTMLAttributes<HTMLAnchorElement>)}
        >
          {content}
        </a>
      );
    }

    if (Component === 'span') {
      return (
        <span
          className={`${baseClass} ${variantClass} ${sizeClass} ${widthClass} ${loadingClass} ${className}`}
          aria-disabled={isDisabled}
          {...props}
        >
          {content}
        </span>
      );
    }

    return (
      <button
        ref={ref}
        type={type}
        className={`${baseClass} ${variantClass} ${sizeClass} ${widthClass} ${loadingClass} ${className}`}
        disabled={isDisabled}
        aria-busy={loading}
        {...props}
      >
        {content}
      </button>
    );
  }
);

Button.displayName = 'Button';