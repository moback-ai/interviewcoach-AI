// components/ui/Button.jsx
import React from 'react';
import { Link } from 'react-router-dom';
import clsx from 'clsx';

function Button({ to, children, variant = 'primary', className = '', ...props }) {
  const baseClasses = 'inline-flex items-center justify-center px-5 py-3 text-sm font-medium transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 rounded-xl';

  const variants = {
    primary: 'bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] text-white shadow-md hover:brightness-110',
    secondary: 'bg-border dark:bg-white/10 text-text hover:bg-white/20 dark:hover:bg-white/20 border border-border',
  };

  return to ? (
    <Link
      to={to}
      className={clsx(baseClasses, variants[variant], className)}
      {...props}
    >
      {children}
    </Link>
  ) : (
    <button
      className={clsx(baseClasses, variants[variant], className)}
      {...props}
    >
      {children}
    </button>
  );
}

export default Button;
