import { useToastStore, type ToastPosition } from '../../../store/toastStore';
import './Toast.css';

const positionClasses: Record<ToastPosition, string> = {
  'top-right': 'toast-container-top-right',
  'top-left': 'toast-container-top-left',
  'bottom-right': 'toast-container-bottom-right',
  'bottom-left': 'toast-container-bottom-left',
  'top-center': 'toast-container-top-center',
  'bottom-center': 'toast-container-bottom-center',
};

export const Toast: React.FC = () => {
  const { toasts, removeToast } = useToastStore();

  const toastsByPosition = toasts.reduce<Record<ToastPosition, typeof toasts>>(
    (acc, toast) => {
      const pos = toast.position || 'bottom-right';
      if (!acc[pos]) acc[pos] = [];
      acc[pos].push(toast);
      return acc;
    },
    {} as Record<ToastPosition, typeof toasts>
  );

  return (
    <>
      {Object.entries(toastsByPosition).map(([position, positionToasts]) => (
        <div
          key={position}
          className={`toast-container ${positionClasses[position as ToastPosition]}`}
        >
          {positionToasts.map((toast) => (
            <div
              key={toast.id}
              className={`toast toast-${toast.type}`}
              role="alert"
            >
              <span className="toast-message">{toast.message}</span>
              <button
                className="toast-close"
                onClick={() => removeToast(toast.id)}
                aria-label="Close"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      ))}
    </>
  );
};