'use client';

import * as React from 'react';
import { Dialog } from '@headlessui/react';
import { cn } from '@/lib/utils/cn';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}

export function Modal({ isOpen, onClose, title, children, size = 'md' }: ModalProps) {
  const sizes = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
  };

  return (
    <Dialog open={isOpen} onClose={onClose} className="relative z-50">
      <div className="fixed inset-0 bg-black/30" aria-hidden="true" />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <Dialog.Panel className={cn('mx-auto rounded-lg bg-background-surface shadow-xl', sizes[size])}>
          {title && (
            <Dialog.Title className="text-lg font-bold p-6 pb-2">
              {title}
            </Dialog.Title>
          )}
          <div className="p-6">{children}</div>
        </Dialog.Panel>
      </div>
    </Dialog>
  );
}