import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

const ThemeContext = createContext(null);

const THEME_STORAGE_KEY = 'theme-preference';
const THEME_EVENT_NAME = 'theme-change';
const AUTO_LIGHT_START_HOUR = 6;
const AUTO_DARK_START_HOUR = 18;

const sanitizePreference = (value) => {
  if (value === 'light' || value === 'dark') {
    return value;
  }
  return 'auto';
};

const resolveAutoTheme = (date = new Date()) => {
  const hour = date.getHours();
  return hour >= AUTO_LIGHT_START_HOUR && hour < AUTO_DARK_START_HOUR
    ? 'light'
    : 'dark';
};

const resolveTheme = (preference) => (
  preference === 'auto' ? resolveAutoTheme() : preference
);

const getInitialPreference = () => {
  if (typeof window === 'undefined') {
    return 'auto';
  }

  return sanitizePreference(window.localStorage.getItem(THEME_STORAGE_KEY));
};

export function ThemeProvider({ children }) {
  const [themePreference, setThemePreferenceState] = useState(getInitialPreference);
  const [theme, setTheme] = useState(() => resolveTheme(getInitialPreference()));

  useEffect(() => {
    const applyResolvedTheme = () => {
      const nextTheme = resolveTheme(themePreference);
      setTheme((currentTheme) => (currentTheme === nextTheme ? currentTheme : nextTheme));
      document.documentElement.classList.toggle('dark', nextTheme === 'dark');
      document.documentElement.dataset.themePreference = themePreference;
      window.localStorage.setItem(THEME_STORAGE_KEY, themePreference);
      window.dispatchEvent(new CustomEvent(THEME_EVENT_NAME, {
        detail: { theme: nextTheme, preference: themePreference },
      }));
    };

    applyResolvedTheme();

    if (themePreference !== 'auto') {
      return undefined;
    }

    const intervalId = window.setInterval(applyResolvedTheme, 60 * 1000);
    return () => window.clearInterval(intervalId);
  }, [themePreference]);

  useEffect(() => {
    const handleStorage = (event) => {
      if (event.key === THEME_STORAGE_KEY) {
        setThemePreferenceState(sanitizePreference(event.newValue));
      }
    };

    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  const setThemePreference = (valueOrUpdater) => {
    setThemePreferenceState((currentPreference) => sanitizePreference(
      typeof valueOrUpdater === 'function'
        ? valueOrUpdater(currentPreference)
        : valueOrUpdater
    ));
  };

  const toggleTheme = () => {
    setThemePreference((currentPreference) => (
      resolveTheme(currentPreference) === 'dark' ? 'light' : 'dark'
    ));
  };

  const value = useMemo(() => ({
    theme,
    themePreference,
    isDark: theme === 'dark',
    isAuto: themePreference === 'auto',
    toggleTheme,
    setThemePreference,
    resetThemePreference: () => setThemePreference('auto'),
  }), [theme, themePreference]);

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);

  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }

  return context;
}
