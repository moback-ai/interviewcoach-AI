import { useEffect, useState } from 'react';

export function useTheme() {
  const [theme, setTheme] = useState(() => {
    if (typeof window === 'undefined') return 'light'; // for SSR

    const stored = localStorage.getItem('theme');
    if (stored) return stored;

    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    return prefersDark ? 'dark' : 'light';
  });

  // Apply theme to <html> element and store it
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('theme', theme);

    // Broadcast theme change with detail
    window.dispatchEvent(new CustomEvent('theme-change', { detail: theme }));
  }, [theme]);

  // Optional: Listen for external theme change (e.g., from another tab)
  useEffect(() => {
    const handler = (e) => {
      if (e?.detail && typeof e.detail === 'string') {
        setTheme(e.detail);
      }
    };

    window.addEventListener('theme-change', handler);
    return () => window.removeEventListener('theme-change', handler);
  }, []);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
  };

  return {
    theme,
    toggleTheme,
    isDark: theme === 'dark',
  };
}
