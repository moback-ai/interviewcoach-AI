/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class', // ✅ VERY important
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: 'var(--color-primary)',
        bg: 'var(--color-bg)',
        text: 'var(--color-text-primary)',
        textSecondary: 'var(--color-text-secondary)',
        accent: 'var(--color-accent)',
        error: 'var(--color-error)',
        border: 'var(--color-border)',
      },
    },
  },
  plugins: [],
};
