/**
 * Force-clear body/html scroll locks left by modals after client-side navigation.
 */
export function unlockBodyScroll() {
  if (typeof document === 'undefined' || typeof window === 'undefined') {
    return;
  }

  const scrollY = Math.abs(parseInt(document.body.style.top || '0', 10)) || window.scrollY;

  document.documentElement.style.overflow = '';
  document.body.style.overflow = '';
  document.body.style.position = '';
  document.body.style.top = '';
  document.body.style.width = '';

  window.scrollTo(0, scrollY);
}
