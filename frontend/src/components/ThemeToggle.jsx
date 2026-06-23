import React from 'react';
import { useTheme } from '../hooks/useTheme';

function ThemeToggle({ disabled = false }) {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      type="button"
      onClick={() => !disabled && toggleTheme()}
      disabled={disabled}
      title={disabled ? 'Theme toggle unavailable during processing' : 'Toggle Theme'}
      aria-disabled={disabled}
      className={`w-8 h-8 sm:w-9 sm:h-9 flex items-center justify-center rounded-full border-2 transition-all duration-200 ${
        disabled
          ? 'border-[var(--color-text-secondary)] opacity-60 cursor-not-allowed'
          : 'border-[var(--color-primary)] hover:bg-[var(--color-input-bg)] cursor-pointer'
      }`}
    >
      <span className="text-lg">
        {theme === 'dark' ? '🌙' : '🌞'}
      </span>
    </button>
  );
}

export default ThemeToggle;
