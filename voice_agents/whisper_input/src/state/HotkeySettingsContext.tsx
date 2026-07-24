import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { getHotkeyCapability, getSettings, isTauri, setSettings } from '../lib/ipc';
import { normalizeLegacyOutputLanguagePrefs } from '../lib/settingsVisibility';
import type { HotkeyBinding, HotkeyCapability, UserPreferences } from '../lib/types';
import { getStoredOutputLanguagePreference } from '../i18n';

interface HotkeySettingsContextValue {
  prefs: UserPreferences | null;
  hotkey: HotkeyBinding | null;
  capability: HotkeyCapability | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  updatePrefs: (
    next: UserPreferences | ((current: UserPreferences) => UserPreferences),
  ) => Promise<void>;
}

const HotkeySettingsContext = createContext<HotkeySettingsContextValue | null>(null);

const errorMessage = (error: unknown) =>
  String(error instanceof Error ? error.message : error);

export function HotkeySettingsProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<UserPreferences | null>(null);
  const [capability, setCapability] = useState<HotkeyCapability | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const persistQueueRef = useRef<Promise<void>>(Promise.resolve());
  const latestPrefsRef = useRef<UserPreferences | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [prefsResult, capabilityResult] = await Promise.allSettled([
        getSettings(),
        getHotkeyCapability(),
      ]);
      let nextError: string | null = null;
      if (prefsResult.status === 'fulfilled') {
        const normalized = normalizeLegacyOutputLanguagePrefs(
          prefsResult.value,
          getStoredOutputLanguagePreference(),
        );
        latestPrefsRef.current = normalized.prefs;
        setPrefs(normalized.prefs);
        if (normalized.changed) {
          try {
            await setSettings(normalized.prefs);
          } catch (error) {
            console.error('[hotkey-settings] failed to normalize legacy output preferences', error);
            nextError = errorMessage(error);
          }
        }
      } else {
        console.error('[hotkey-settings] failed to load preferences', prefsResult.reason);
        nextError = errorMessage(prefsResult.reason);
      }
      if (capabilityResult.status === 'fulfilled') {
        setCapability(capabilityResult.value);
      } else {
        console.error('[hotkey-settings] failed to load hotkey capability', capabilityResult.reason);
        nextError = errorMessage(capabilityResult.reason);
      }
      setError(nextError);
    } catch (error) {
      console.error('[hotkey-settings] failed to refresh hotkey settings', error);
      setError(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }, []);

  const queueSetSettings = useCallback((resolveNext: (current: UserPreferences) => UserPreferences) => {
    const task = persistQueueRef.current
      .catch(() => undefined)
      .then(async () => {
        const current = latestPrefsRef.current;
        if (!current) return;
        const next = resolveNext(current);
        await setSettings(next);
      });
    persistQueueRef.current = task;
    return task;
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!isTauri) return;
    let cancelled = false;
    let unlisten: (() => void) | undefined;
    void (async () => {
      try {
        const { listen } = await import('@tauri-apps/api/event');
        const handle = await listen<UserPreferences>('prefs:changed', event => {
          const nextPrefs = event.payload;
          if (!nextPrefs) return;
          latestPrefsRef.current = nextPrefs;
          setPrefs(nextPrefs);
        });
        if (cancelled) {
          handle();
        } else {
          unlisten = handle;
        }
      } catch (error) {
        console.warn('[settings] prefs:changed listener setup failed', error);
      }
    })();
    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, []);

  useEffect(() => {
    latestPrefsRef.current = prefs;
  }, [prefs]);

  const updatePrefs = useCallback(
    async (next: UserPreferences | ((current: UserPreferences) => UserPreferences)) => {
      const current = latestPrefsRef.current;
      if (!current) return;
      const resolved = typeof next === 'function' ? next(current) : next;
      setPrefs(resolved);
      latestPrefsRef.current = resolved;
      await queueSetSettings(() => resolved);
    },
    [queueSetSettings],
  );

  const value = useMemo<HotkeySettingsContextValue>(
    () => ({
      prefs,
      hotkey: prefs?.hotkey ?? null,
      capability,
      loading,
      error,
      refresh,
      updatePrefs,
    }),
    [capability, error, loading, prefs, refresh, updatePrefs],
  );

  return <HotkeySettingsContext.Provider value={value}>{children}</HotkeySettingsContext.Provider>;
}

export function useHotkeySettings() {
  const value = useContext(HotkeySettingsContext);
  if (!value) {
    throw new Error('useHotkeySettings must be used within HotkeySettingsProvider');
  }
  return value;
}
