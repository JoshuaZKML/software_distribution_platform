import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

export type ToastType = 'info' | 'success' | 'warning' | 'error';
export type ToastPosition = 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left' | 'top-center' | 'bottom-center';

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
  position?: ToastPosition;
}

interface ToastStore {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
  clearToasts: () => void;
}

export const useToastStore = create<ToastStore>()(
  devtools(
    (set) => ({
      toasts: [],
      addToast: (toast) => {
        const id = Math.random().toString(36).substring(2, 9);
        const position = toast.position || 'bottom-right';
        set((state) => ({
          toasts: [...state.toasts, { ...toast, id, position }],
        }));
        if (toast.duration !== 0) {
          setTimeout(() => {
            set((state) => ({
              toasts: state.toasts.filter((t) => t.id !== id),
            }));
          }, toast.duration || 5000);
        }
      },
      removeToast: (id) =>
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        })),
      clearToasts: () => set({ toasts: [] }),
    }),
    { name: 'ToastStore' }
  )
);