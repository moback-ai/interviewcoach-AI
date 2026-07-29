import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { FiAlertCircle, FiAlertTriangle, FiInfo, FiLayers } from 'react-icons/fi';

const VARIANTS = {
  error: {
    icon: FiAlertCircle,
    iconWrap: 'bg-red-100 dark:bg-red-900/30',
    iconColor: 'text-red-600 dark:text-red-400',
    accentBar: 'from-red-500/80 to-red-400/40',
    button: 'bg-red-600 hover:bg-red-700 shadow-red-600/20',
  },
  info: {
    icon: FiInfo,
    iconWrap: 'bg-blue-100 dark:bg-blue-900/30',
    iconColor: 'text-blue-600 dark:text-blue-400',
    accentBar: 'from-[var(--color-primary)]/80 to-[var(--color-accent)]/50',
    button: 'bg-[var(--color-primary)] hover:opacity-90 shadow-[var(--color-primary)]/25',
  },
  warning: {
    icon: FiAlertTriangle,
    iconWrap: 'bg-amber-100 dark:bg-amber-900/30',
    iconColor: 'text-amber-600 dark:text-amber-400',
    accentBar: 'from-amber-500/90 to-orange-400/50',
    button: 'bg-[var(--color-primary)] hover:opacity-90 shadow-[var(--color-primary)]/25',
  },
  existing: {
    icon: FiLayers,
    iconWrap: 'bg-[color-mix(in_srgb,var(--color-primary)_14%,transparent)]',
    iconColor: 'text-[var(--color-primary)]',
    accentBar: 'from-[var(--color-primary)] to-[var(--color-accent)]',
    button: 'bg-[var(--color-primary)] hover:opacity-90 shadow-[var(--color-primary)]/25',
  },
};

const NoticeModal = ({
  isOpen,
  onClose,
  title,
  message,
  variant = 'error',
  primaryLabel = 'OK',
  onPrimary,
  secondaryLabel,
  onSecondary,
  details,
  actionButton = null,
}) => {
  const styles = VARIANTS[variant] || VARIANTS.error;
  const Icon = styles.icon;
  const hasSecondary = Boolean(secondaryLabel && onSecondary);
  const isRich = variant === 'existing' || variant === 'warning';
  const handlePrimary = onPrimary || onClose;

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

    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKeyDown);

    return () => {
      document.documentElement.style.overflow = original.htmlOverflow;
      document.body.style.overflow = original.bodyOverflow;
      document.body.style.position = original.bodyPosition;
      document.body.style.top = original.bodyTop;
      document.body.style.width = original.bodyWidth;
      window.removeEventListener('keydown', onKeyDown);
      window.scrollTo(0, scrollY);
    };
  }, [isOpen, onClose]);

  if (!isOpen || typeof document === 'undefined') return null;

  const defaultTitle =
    variant === 'error'
      ? 'Something went wrong'
      : variant === 'existing'
        ? 'Pair already prepared'
        : 'Notice';

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/55 backdrop-blur-[3px] p-3 sm:p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose?.();
      }}
    >
      <div
        className={`relative w-full overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] shadow-2xl mx-auto notice-modal-enter ${
          isRich ? 'max-w-md sm:max-w-lg' : 'max-w-xs sm:max-w-sm md:max-w-md'
        }`}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="notice-modal-title"
        aria-describedby="notice-modal-message"
      >
        <div className={`h-1.5 w-full bg-gradient-to-r ${styles.accentBar}`} />

        <div className={`flex items-start gap-3 sm:gap-4 ${isRich ? 'p-5 sm:p-6 pb-3 sm:pb-4' : 'p-3 sm:p-4 md:p-6 border-b border-[var(--color-border)]'}`}>
          <div
            className={`rounded-2xl flex items-center justify-center shrink-0 ring-1 ring-black/5 dark:ring-white/10 ${styles.iconWrap} ${
              isRich ? 'w-12 h-12 sm:w-14 sm:h-14' : 'w-8 h-8 sm:w-10 sm:h-10 rounded-full'
            }`}
          >
            <Icon className={`${styles.iconColor} ${isRich ? 'w-6 h-6 sm:w-7 sm:h-7' : 'w-4 h-4 sm:w-5 sm:h-5'}`} />
          </div>
          <div className="min-w-0 flex-1 pt-0.5">
            <h3
              id="notice-modal-title"
              className={`font-semibold text-[var(--color-text-primary)] tracking-tight ${
                isRich ? 'text-lg sm:text-xl' : 'text-base sm:text-lg'
              }`}
            >
              {title || defaultTitle}
            </h3>
            {isRich && (
              <p className="mt-1 text-xs sm:text-sm text-[var(--color-text-secondary)]">
                This resume and job description already have questions ready.
              </p>
            )}
          </div>
        </div>

        <div className={isRich ? 'px-5 sm:px-6 pb-5 sm:pb-6' : 'p-3 sm:p-4 md:p-6'}>
          <p
            id="notice-modal-message"
            className="text-sm sm:text-[0.95rem] text-[var(--color-text-secondary)] leading-relaxed"
          >
            {message}
          </p>

          {Array.isArray(details) && details.length > 0 && (
            <div className="mt-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-input-bg)]/80 p-3.5 sm:p-4">
              <ul className="space-y-2.5">
                {details.map((detail, index) => {
                  if (detail && typeof detail === 'object' && (detail.label || detail.value)) {
                    return (
                      <li key={index} className="flex items-start justify-between gap-3 text-sm">
                        <span className="text-[var(--color-text-secondary)] shrink-0">
                          {detail.label}
                        </span>
                        <span className="font-medium text-[var(--color-text-primary)] text-right">
                          {detail.value}
                        </span>
                      </li>
                    );
                  }
                  return (
                    <li key={index} className="text-sm text-[var(--color-text-secondary)]">
                      {detail}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

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
            <div
              className={`mt-5 flex gap-2.5 sm:gap-3 ${
                hasSecondary ? 'flex-col-reverse sm:flex-row' : 'flex-col'
              }`}
            >
              {hasSecondary && (
                <button
                  type="button"
                  onClick={onSecondary}
                  className="w-full py-2.5 sm:py-3 px-4 rounded-xl border border-[var(--color-border)] text-[var(--color-text-primary)] font-semibold text-sm sm:text-base hover:bg-[var(--color-input-bg)] transition-colors"
                >
                  {secondaryLabel}
                </button>
              )}
              <button
                type="button"
                onClick={handlePrimary}
                className={`w-full py-2.5 sm:py-3 px-4 rounded-xl text-white font-semibold text-sm sm:text-base shadow-lg transition-all hover:shadow-xl ${styles.button}`}
              >
                {primaryLabel}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};

export default NoticeModal;
