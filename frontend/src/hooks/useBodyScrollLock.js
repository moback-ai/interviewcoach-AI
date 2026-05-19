import { useEffect } from 'react';

/**
 * Prevents background page scroll while a modal or long-running overlay is open.
 */
export default function useBodyScrollLock(locked) {
  useEffect(() => {
    if (!locked || typeof document === 'undefined' || typeof window === 'undefined') {
      return undefined;
    }

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
  }, [locked]);
}
