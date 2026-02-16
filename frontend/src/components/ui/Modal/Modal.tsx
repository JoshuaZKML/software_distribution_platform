import React, { useEffect, useRef, useCallback } from 'react';
import ReactDOM from 'react-dom';
import * as FocusTrap from 'focus-trap-react';
import './Modal.css';

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  closeOnClickOutside?: boolean;
  closeOnEsc?: boolean;
  initialFocusRef?: React.RefObject<HTMLElement>;
  finalFocusRef?: React.RefObject<HTMLElement>;
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  closeOnClickOutside = true,
  closeOnEsc = true,
  initialFocusRef,
  finalFocusRef,
}) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedElement = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      previouslyFocusedElement.current = document.activeElement as HTMLElement;
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
      if (finalFocusRef?.current) {
        finalFocusRef.current.focus();
      } else if (previouslyFocusedElement.current) {
        previouslyFocusedElement.current.focus();
      }
    }

    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen, finalFocusRef]);

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (closeOnClickOutside && e.target === e.currentTarget) {
        onClose();
      }
    },
    [closeOnClickOutside, onClose]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (closeOnEsc && e.key === 'Escape') {
        onClose();
      }
    },
    [closeOnEsc, onClose]
  );

  if (!isOpen) return null;

  return ReactDOM.createPortal(
    <FocusTrap.default
      active={isOpen}
      focusTrapOptions={{
        initialFocus: initialFocusRef ? initialFocusRef.current || undefined : false,
        clickOutsideDeactivates: closeOnClickOutside,
        escapeDeactivates: closeOnEsc,
        onDeactivate: onClose,
        returnFocusOnDeactivate: false,
      }}
    >
      <div
        className="modal-backdrop"
        onClick={handleBackdropClick}
        onKeyDown={handleKeyDown}
        role="presentation"
      >
        <div
          ref={modalRef}
          className={`modal modal-${size}`}
          role="dialog"
          aria-modal="true"
          aria-labelledby={title ? 'modal-title' : undefined}
          tabIndex={-1}
        >
          {title && (
            <div className="modal-header">
              <h2 id="modal-title" className="modal-title">
                {title}
              </h2>
              <button
                className="modal-close"
                onClick={onClose}
                aria-label="Close"
              >
                ×
              </button>
            </div>
          )}
          <div className="modal-body">{children}</div>
          {footer && <div className="modal-footer">{footer}</div>}
        </div>
      </div>
    </FocusTrap.default>,
    document.body
  );
};