import {
  applyThemePreference,
  readThemePreference,
  setThemePreference,
} from './themePreference';

function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(message);
}

function setGlobalProperty(name: 'window' | 'document', value: unknown): void {
  Object.defineProperty(globalThis, name, {
    value,
    configurable: true,
    writable: true,
  });
}

function removeGlobalProperty(name: 'window' | 'document'): void {
  delete (globalThis as Record<string, unknown>)[name];
}

const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
const originalDocument = Object.getOwnPropertyDescriptor(globalThis, 'document');

function restoreGlobals(): void {
  removeGlobalProperty('window');
  removeGlobalProperty('document');
  if (originalWindow) Object.defineProperty(globalThis, 'window', originalWindow);
  if (originalDocument) Object.defineProperty(globalThis, 'document', originalDocument);
}

try {
  removeGlobalProperty('window');
  removeGlobalProperty('document');
  assert(readThemePreference() === 'light', 'missing window should fall back to light');
  applyThemePreference('dark');
  setThemePreference('dark');

  setGlobalProperty('window', {
    localStorage: {
      getItem: () => null,
      setItem: () => undefined,
    },
    matchMedia: () => ({ matches: true }),
  });
  assert(readThemePreference() === 'dark', 'missing storage should fall back to system dark preference when available');

  setGlobalProperty('window', {
    localStorage: {
      getItem: () => 'unexpected',
      setItem: () => undefined,
    },
    matchMedia: () => ({ matches: false }),
  });
  assert(readThemePreference() === 'light', 'invalid storage should fall back safely');

  setGlobalProperty('window', {
    localStorage: {
      getItem: () => { throw new Error('blocked'); },
      setItem: () => undefined,
    },
    matchMedia: () => ({ matches: true }),
  });
  assert(readThemePreference() === 'light', 'storage read failures should return a safe default');

  setGlobalProperty('window', {
    localStorage: {
      getItem: () => 'light',
      setItem: () => { throw new Error('quota'); },
    },
  });
  setGlobalProperty('document', {
    documentElement: {
      dataset: {},
    },
  });
  setThemePreference('dark');
  assert(true, 'storage write failures should not throw');

  removeGlobalProperty('document');
  applyThemePreference('light');
  setThemePreference('light');
  assert(true, 'document absence should not throw');
} finally {
  restoreGlobals();
}
