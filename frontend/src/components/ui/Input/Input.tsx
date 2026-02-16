import React, { forwardRef, useId } from 'react';
import './Input.css';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  fullWidth?: boolean;
  startAdornment?: React.ReactNode;
  endAdornment?: React.ReactNode;
  helperText?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      error,
      fullWidth = false,
      startAdornment,
      endAdornment,
      helperText,
      className = '',
      id: providedId,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const inputId = providedId || `input-${generatedId}`;
    const errorId = error ? `${inputId}-error` : undefined;
    const helperId = helperText && !error ? `${inputId}-helper` : undefined;
    const describedBy = [errorId, helperId].filter(Boolean).join(' ') || undefined;

    return (
      <div className={`input-wrapper ${fullWidth ? 'input-full-width' : ''}`}>
        {label && (
          <label htmlFor={inputId} className="input-label">
            {label}
          </label>
        )}
        <div className="input-container">
          {startAdornment && <span className="input-adornment input-adornment-start">{startAdornment}</span>}
          <input
            ref={ref}
            id={inputId}
            className={`input-field ${error ? 'input-error' : ''} ${className}`}
            aria-invalid={!!error}
            aria-errormessage={errorId}
            aria-describedby={describedBy}
            {...props}
          />
          {endAdornment && <span className="input-adornment input-adornment-end">{endAdornment}</span>}
        </div>
        {error && (
          <span id={errorId} className="input-error-message" role="alert">
            {error}
          </span>
        )}
        {helperText && !error && (
          <span id={helperId} className="input-helper-text">
            {helperText}
          </span>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';