import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { FiAlertCircle, FiInfo } from 'react-icons/fi';

const VARIANTS = {
  error: {
    icon: FiAlertCircle,
    iconWrap: 'bg-red-100 dark:bg-red-900/20',
    iconColor: 'text-red-600 dark:text-red-400',
    button: 'bg-red-600 hover:bg-red-700',
  },
  info: {
    icon: FiInfo,
    iconWrap: 'bg-blue-100 dark:bg-blue-900/20',
    iconColor: 'text-blue-600 dark:text-blue-400',
    button: 'bg-[var(--color-primary)] hover:opacity-90',
  },
};

const NoticeModal = ({ isOpen, onClose, title, message, variant = 'error', actionButton = null }) => {
  const styles = VARIANTS[variant] || VARIANTS.error;
  const Icon = styles.icon;

  useEffect(() => {
    if (!isOpen || typeof document === 'undefined' || typeof window === 'undefined') return undefined;

    const scrollY = window.scrollY;
    const original = {
      bodyOverflow: document.body.style.overflow,
      bodyPosition: document.body.style.position,
      bodyTop: document.body.style.top,
      bodyWidth: document.body.style.width,
      htmlOverflow: document.documentElement.style.overflow,
    };

    document.documentElement.style.overflow = 'hidden';
    document.body.style.overflow = 'hidden';
    document.body.style.position = 'fixed';
    document.body.style.top = `-${scrollY}px`;
    document.body.style.width = '100%';

    return () => {
      document.documentElement.style.overflow = original.htmlOverflow;
      document.body.style.overflow = original.bodyOverflow;
      document.body.style.position = original.bodyPosition;
      document.body.style.top = original.bodyTop;
      document.body.style.width = original.bodyWidth;
      window.scrollTo(0, scrollY);
    };
  }, [isOpen]);

  if (!isOpen || typeof document === 'undefined') return null;

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-2 sm:p-4">
      <div
        className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl w-full max-w-xs sm:max-w-sm md:max-w-md shadow-2xl mx-2"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="notice-modal-title"
      >
        <div className="flex items-center gap-2 sm:gap-3 p-3 sm:p-4 md:p-6 border-b border-[var(--color-border)]">
          <div className={`w-8 h-8 sm:w-10 sm:h-10 rounded-full flex items-center justify-center shrink-0 ${styles.iconWrap}`}>
            <Icon className={`w-4 h-4 sm:w-5 sm:h-5 ${styles.iconColor}`} />
          </div>
          <h3 id="notice-modal-title" className="text-base sm:text-lg font-semibold text-[var(--color-text-primary)]">
            {title || (variant === 'error' ? 'Something went wrong' : 'Notice')}
          </h3>
        </div>
        <div className="p-3 sm:p-4 md:p-6">
          <p className="text-sm sm:text-base text-[var(--color-text-secondary)] leading-relaxed">{message}</p>
          {actionButton ? (
            <div className="mt-4 flex flex-col sm:flex-row gap-2">
              {actionButton}
              <button
                type="button"
                onClick={onClose}
                className="w-full sm:w-auto py-2.5 px-4 rounded-lg bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200 font-semibold hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
              >
                Close
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={onClose}
              className={`mt-4 w-full py-2.5 px-4 rounded-lg text-white font-semibold transition-colors ${styles.button}`}
            >
              OK
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};

export default NoticeModal;
