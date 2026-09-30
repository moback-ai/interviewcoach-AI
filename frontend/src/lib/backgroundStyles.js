export const BACKGROUND_STYLE_STORAGE_KEY = 'interviewcoach-selected-background-style';

/** Catalog used by the style lab and (later) app-wide backgrounds. */
export const BACKGROUND_STYLES = [
  {
    id: 'ocean-waves',
    name: 'Ocean Waves',
    tagline: 'Bold interactive waves — Dribbble-style login hero',
    category: 'Interactive',
    vantaPreset: 'auth',
    shell: 'auth-studio',
    thumbClass: 'bg-style-thumb-ocean-waves',
    recommendedFor: 'Login, Sign up, Upload, Dashboard, Profile, FAQ, Landing',
  },
  {
    id: 'soft-cloud',
    name: 'Soft Cloud',
    tagline: 'Light airy waves — default app pages',
    category: 'Interactive',
    vantaPreset: 'subtle',
    shell: 'page-waves',
    thumbClass: 'bg-style-thumb-soft-cloud',
    recommendedFor: 'Upload, Dashboard, Profile',
  },
  {
    id: 'calm-upload',
    name: 'Calm Upload',
    tagline: 'Gentle motion tuned for forms and file uploads',
    category: 'Interactive',
    vantaPreset: 'upload',
    shell: 'page-waves',
    thumbClass: 'bg-style-thumb-calm-upload',
    recommendedFor: 'Upload, long forms',
  },
  {
    id: 'landing-breeze',
    name: 'Landing Breeze',
    tagline: 'Marketing-friendly waves with a bright feel',
    category: 'Interactive',
    vantaPreset: 'landing',
    shell: 'page-waves',
    thumbClass: 'bg-style-thumb-landing-breeze',
    recommendedFor: 'Landing, FAQ',
  },
  {
    id: 'aurora-dream',
    name: 'Aurora Dream',
    tagline: 'CSS-only drifting orbs — no WebGL, very smooth',
    category: 'CSS only',
    shell: 'css',
    cssClass: 'bg-style-aurora-dream',
    thumbClass: 'bg-style-thumb-aurora-dream',
    recommendedFor: 'All pages (performance)',
  },
  {
    id: 'midnight-grid',
    name: 'Midnight Grid',
    tagline: 'Deep navy gradient with subtle tech grid',
    category: 'CSS only',
    shell: 'css',
    cssClass: 'bg-style-midnight-grid',
    thumbClass: 'bg-style-thumb-midnight-grid',
    recommendedFor: 'Dark mode, dashboard',
  },
  {
    id: 'sunset-glow',
    name: 'Sunset Glow',
    tagline: 'Warm coral and violet ambient light',
    category: 'CSS only',
    shell: 'css',
    cssClass: 'bg-style-sunset-glow',
    thumbClass: 'bg-style-thumb-sunset-glow',
    recommendedFor: 'Landing, marketing',
  },
  {
    id: 'minimal-glass',
    name: 'Minimal Glass',
    tagline: 'Barely-there gradient — content stays in focus',
    category: 'CSS only',
    shell: 'css',
    cssClass: 'bg-style-minimal-glass',
    thumbClass: 'bg-style-thumb-minimal-glass',
    recommendedFor: 'Interview feedback, dense UI',
  },
];

export const DEFAULT_BACKGROUND_STYLE_ID = 'aurora-dream';

/** Protected app pages — CSS-only aurora (no WebGL). */
export const APP_BACKGROUND_STYLE_ID = 'aurora-dream';

export function getBackgroundStyleById(styleId) {
  return BACKGROUND_STYLES.find((style) => style.id === styleId)
    || BACKGROUND_STYLES.find((style) => style.id === DEFAULT_BACKGROUND_STYLE_ID);
}

export function getSelectedBackgroundStyleId() {
  if (typeof window === 'undefined') {
    return DEFAULT_BACKGROUND_STYLE_ID;
  }
  const stored = window.localStorage.getItem(BACKGROUND_STYLE_STORAGE_KEY);
  return getBackgroundStyleById(stored)?.id || DEFAULT_BACKGROUND_STYLE_ID;
}

export function setSelectedBackgroundStyleId(styleId) {
  if (typeof window === 'undefined') {
    return getBackgroundStyleById(styleId)?.id || DEFAULT_BACKGROUND_STYLE_ID;
  }
  const resolved = getBackgroundStyleById(styleId)?.id || DEFAULT_BACKGROUND_STYLE_ID;
  window.localStorage.setItem(BACKGROUND_STYLE_STORAGE_KEY, resolved);
  return resolved;
}
