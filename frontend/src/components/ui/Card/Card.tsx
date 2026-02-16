import React from 'react';
import './Card.css';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  bordered?: boolean;
  hoverable?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  padding = 'md',
  bordered = true,
  hoverable = false,
}) => {
  const paddingClass = `card-padding-${padding}`;
  return (
    <div
      className={`card ${paddingClass} ${bordered ? 'card-bordered' : ''} ${
        hoverable ? 'card-hoverable' : ''
      } ${className}`}
    >
      {children}
    </div>
  );
};