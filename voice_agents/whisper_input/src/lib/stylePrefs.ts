import type { PolishMode, UserPreferences } from './types';

type StylePrefsState = UserPreferences | null;
type StylePrefsSetter = (prefs: StylePrefsState | ((current: StylePrefsState) => StylePrefsState)) => void;
type StylePrefsRollback = (current: StylePrefsState) => StylePrefsState;

export function styleSaveErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return String(error);
}

export async function persistStylePreferenceChange(
  nextPrefs: UserPreferences,
  persist: () => Promise<void>,
  setPrefs: StylePrefsSetter,
  onFailure: (message: string) => void,
  rollback: StylePrefsRollback,
): Promise<boolean> {
  setPrefs(nextPrefs);
  try {
    await persist();
    return true;
  } catch (error) {
    setPrefs(current => rollback(current));
    onFailure(styleSaveErrorMessage(error));
    return false;
  }
}

export function applyStylePreferencesNotification(
  _current: UserPreferences | null,
  incoming: UserPreferences,
): UserPreferences {
  return incoming;
}

export function styleMasterFallbackModes(defaultMode: PolishMode): PolishMode[] {
  return defaultMode === 'raw' ? ['raw'] : ['raw', defaultMode];
}

export function isStyleMasterEnabled(prefs: UserPreferences): boolean {
  return !sameModeSet(prefs.enabledModes, styleMasterFallbackModes(prefs.defaultMode));
}

export function styleMasterOffPreferences(prefs: UserPreferences): UserPreferences {
  return { ...prefs, enabledModes: styleMasterFallbackModes(prefs.defaultMode) };
}

export function styleDefaultModePreferences(prefs: UserPreferences, mode: PolishMode): UserPreferences {
  const enabledModes = prefs.enabledModes.includes(mode)
    ? prefs.enabledModes
    : [...prefs.enabledModes, mode];
  const nextPrefs = { ...prefs, defaultMode: mode, enabledModes };
  return isStyleMasterEnabled(prefs) ? nextPrefs : styleMasterOffPreferences(nextPrefs);
}

export function rollbackDefaultModeChange(
  previousPrefs: UserPreferences,
  nextPrefs: UserPreferences,
): StylePrefsRollback {
  return current => {
    if (!current || current.defaultMode !== nextPrefs.defaultMode) return current;
    return { ...current, defaultMode: previousPrefs.defaultMode };
  };
}

export function rollbackStyleEnabledChange(
  mode: PolishMode,
  previousPrefs: UserPreferences,
  nextPrefs: UserPreferences,
): StylePrefsRollback {
  const previousEnabled = previousPrefs.enabledModes.includes(mode);
  const nextEnabled = nextPrefs.enabledModes.includes(mode);
  return current => {
    if (!current || current.enabledModes.includes(mode) !== nextEnabled) return current;
    const enabledModes = previousEnabled
      ? Array.from(new Set([...current.enabledModes, mode]))
      : current.enabledModes.filter(m => m !== mode);
    return { ...current, enabledModes };
  };
}

export function rollbackWholeStylePreferences(
  previousPrefs: UserPreferences,
  nextPrefs: UserPreferences,
): StylePrefsRollback {
  return current => {
    if (!current || !sameModes(current.enabledModes, nextPrefs.enabledModes)) return current;
    return { ...current, enabledModes: previousPrefs.enabledModes };
  };
}

export function rollbackDefaultAndEnabledChange(
  previousPrefs: UserPreferences,
  nextPrefs: UserPreferences,
): StylePrefsRollback {
  return current => {
    if (
      !current ||
      current.defaultMode !== nextPrefs.defaultMode ||
      !sameModes(current.enabledModes, nextPrefs.enabledModes)
    ) {
      return current;
    }
    return {
      ...current,
      defaultMode: previousPrefs.defaultMode,
      enabledModes: previousPrefs.enabledModes,
    };
  };
}

function sameModeSet(left: PolishMode[], right: PolishMode[]): boolean {
  if (left.length !== right.length) return false;
  const rightSet = new Set(right);
  return left.every(mode => rightSet.has(mode));
}

function sameModes(left: PolishMode[], right: PolishMode[]): boolean {
  if (left.length !== right.length) return false;
  return left.every((mode, index) => mode === right[index]);
}
