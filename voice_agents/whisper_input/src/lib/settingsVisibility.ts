import {
  DOUBAO_LLM_PROVIDER_ID,
  GEMINI_PROVIDER_ID,
  OPENAI_COMPATIBLE_PROVIDER_ID,
  QWEN_LLM_PROVIDER_ID,
} from './product';
import type { OutputLanguagePreference, UserPreferences } from './types';

export const STANDARD_SETTINGS_SECTION_IDS = ['models', 'recording', 'privacy', 'output', 'about'] as const;

export type StandardLlmProviderId =
  | typeof QWEN_LLM_PROVIDER_ID
  | typeof DOUBAO_LLM_PROVIDER_ID
  | typeof GEMINI_PROVIDER_ID;
export type VisibleLlmProviderId =
  | typeof QWEN_LLM_PROVIDER_ID
  | typeof DOUBAO_LLM_PROVIDER_ID
  | typeof GEMINI_PROVIDER_ID
  | typeof OPENAI_COMPATIBLE_PROVIDER_ID;
export const OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY = 'openai-compatible:active';
export type VisibleLlmPresetSelection = string | typeof OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY;
type OutputLanguagePrefs = Pick<
  UserPreferences,
  'chineseScriptPreference' | 'outputLanguagePreference' | 'outputLanguagePreferenceExplicit'
>;
type NormalizedOutputLanguagePrefs<T extends OutputLanguagePrefs> = Omit<
  T,
  keyof OutputLanguagePrefs
> &
  OutputLanguagePrefs;

export function visibleStandardLlmProviderIds(): StandardLlmProviderId[] {
  return [QWEN_LLM_PROVIDER_ID, DOUBAO_LLM_PROVIDER_ID, GEMINI_PROVIDER_ID];
}

export function providerSwitchControlsDisabled(isSwitching: boolean): boolean {
  return isSwitching;
}

export function normalizeStandardLlmProvider(id: string | null | undefined): StandardLlmProviderId {
  if (id === GEMINI_PROVIDER_ID) return id;
  if (id === DOUBAO_LLM_PROVIDER_ID) return id;
  return QWEN_LLM_PROVIDER_ID;
}

export function normalizeVisibleLlmProvider(id: string | null | undefined): VisibleLlmProviderId {
  if (id === GEMINI_PROVIDER_ID || id === DOUBAO_LLM_PROVIDER_ID || id === OPENAI_COMPATIBLE_PROVIDER_ID) {
    return id;
  }
  return QWEN_LLM_PROVIDER_ID;
}

export function settingsVisibleLocaleOptions(): Array<'zh-CN' | 'en'> {
  return ['zh-CN', 'en'];
}

export function settingsVisibleOutputLanguageOptions(): Array<'zhCn' | 'en'> {
  return ['zhCn', 'en'];
}

export function llmPresetSelectionForVisibleProvider<T extends string>(
  providerId: string | null | undefined,
  standardPresetKey: T,
): T | typeof OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY {
  return normalizeVisibleLlmProvider(providerId) === OPENAI_COMPATIBLE_PROVIDER_ID
    ? OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY
    : standardPresetKey;
}

export function isAdvancedOpenAiCompatibleConfigVisible(
  activeLlmProvider: string | null | undefined,
  advancedOpen: boolean,
): boolean {
  return advancedOpen || activeLlmProvider === OPENAI_COMPATIBLE_PROVIDER_ID;
}

export function outputPrefsPatchForUiLanguageChange(): Pick<
  UserPreferences,
  'chineseScriptPreference' | 'outputLanguagePreference' | 'outputLanguagePreferenceExplicit'
> | null {
  return null;
}

function patchForOutputLanguagePreference(
  preference: Extract<OutputLanguagePreference, 'auto' | 'zhCn' | 'zhTw' | 'en'>,
): OutputLanguagePrefs {
  if (preference === 'zhCn') {
    return {
      chineseScriptPreference: 'simplified',
      outputLanguagePreference: 'zhCn',
      outputLanguagePreferenceExplicit: true,
    };
  }
  if (preference === 'zhTw') {
    return {
      chineseScriptPreference: 'traditional',
      outputLanguagePreference: 'zhTw',
      outputLanguagePreferenceExplicit: true,
    };
  }
  return {
    chineseScriptPreference: 'auto',
    outputLanguagePreference: preference,
    outputLanguagePreferenceExplicit: true,
  };
}

export function normalizeLegacyOutputLanguagePrefs<T extends OutputLanguagePrefs>(
  prefs: T,
  explicitOutputLanguagePreference: Extract<OutputLanguagePreference, 'auto' | 'zhCn' | 'zhTw' | 'en'> | null,
): { prefs: NormalizedOutputLanguagePrefs<T>; changed: boolean } {
  if (explicitOutputLanguagePreference) {
    const patch = patchForOutputLanguagePreference(explicitOutputLanguagePreference);
    const changed =
      prefs.chineseScriptPreference !== patch.chineseScriptPreference ||
      prefs.outputLanguagePreference !== patch.outputLanguagePreference ||
      prefs.outputLanguagePreferenceExplicit !== true;
    return {
      prefs: { ...prefs, ...patch },
      changed,
    };
  }
  if (prefs.outputLanguagePreferenceExplicit) {
    return { prefs: prefs as NormalizedOutputLanguagePrefs<T>, changed: false };
  }
  if (
    prefs.outputLanguagePreference === 'auto' &&
    prefs.chineseScriptPreference === 'auto' &&
    !prefs.outputLanguagePreferenceExplicit
  ) {
    return { prefs: prefs as NormalizedOutputLanguagePrefs<T>, changed: false };
  }
  return {
    prefs: {
      ...prefs,
      chineseScriptPreference: 'auto',
      outputLanguagePreference: 'auto',
      outputLanguagePreferenceExplicit: false,
    },
    changed: true,
  };
}
