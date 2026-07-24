export type ThemePreference = 'light' | 'dark';

const THEME_STORAGE_KEY = 'ol.theme';

function systemThemePreference(): ThemePreference {
  try {
    if (typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
  } catch {
    // Ignore restricted matchMedia access and use the stable default below.
  }
  return 'light';
}

export function readThemePreference(): ThemePreference {
  try {
    if (typeof window === 'undefined') return 'light';
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === 'dark' || stored === 'light') return stored;
    return systemThemePreference();
  } catch {
    return 'light';
  }
}

export function applyThemePreference(theme: ThemePreference): void {
  try {
    if (typeof document === 'undefined') return;
    document.documentElement.dataset.theme = theme;
  } catch {
    // Ignore restricted document access.
  }
}

export function setThemePreference(theme: ThemePreference): void {
  applyThemePreference(theme);
  try {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Ignore restricted or quota-limited storage.
  }
}
