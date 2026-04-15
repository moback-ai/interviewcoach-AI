import React from 'react';
import { useTheme } from '../hooks/useTheme';

function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      title="Toggle Theme"
      className="w-8 h-8 sm:w-9 sm:h-9 flex items-center justify-center rounded-full border-2 border-[var(--color-primary)] hover:bg-[var(--color-input-bg)] transition-all duration-200"
    >
      <span className="text-lg">
        {theme === 'dark' ? '🌙' : '🌞'}
      </span>
    </button>
  );
}

export default ThemeToggle;
