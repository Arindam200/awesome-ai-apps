import {
  OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY,
  isAdvancedOpenAiCompatibleConfigVisible,
  llmPresetSelectionForVisibleProvider,
  normalizeLegacyOutputLanguagePrefs,
  normalizeVisibleLlmProvider,
  outputPrefsPatchForUiLanguageChange,
  providerSwitchControlsDisabled,
  settingsVisibleLocaleOptions,
  settingsVisibleOutputLanguageOptions,
  STANDARD_SETTINGS_SECTION_IDS,
  visibleStandardLlmProviderIds,
} from './settingsVisibility';
import { ASR_PROVIDER_PRESETS, LLM_MODEL_PRESETS } from './providerPresets';
import {
  DOUBAO_LLM_PROVIDER_ID,
  GEMINI_PROVIDER_ID,
  OPENAI_COMPATIBLE_PROVIDER_ID,
  QWEN_LLM_PROVIDER_ID,
} from './product';
import { PRODUCT_FEATURES } from './productMode';

function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(message);
}

const standardLlmIds = visibleStandardLlmProviderIds();

assert(
  STANDARD_SETTINGS_SECTION_IDS.join(',') === 'models,recording,privacy,output,about',
  `standard settings sections should be models,recording,privacy,output,about, got ${STANDARD_SETTINGS_SECTION_IDS.join(',')}`,
);
assert(
  PRODUCT_FEATURES.showLocalAsrExperiments === false,
  'standard product mode must not expose local ASR experiments',
);
assert(
  PRODUCT_FEATURES.showFoundryLocalAsr === false,
  'standard product mode must not expose Foundry Local ASR',
);
assert(
  PRODUCT_FEATURES.showQwenLocalAsr === false,
  'standard product mode must not expose Qwen local ASR',
);
assert(
  standardLlmIds.join(',') === `${QWEN_LLM_PROVIDER_ID},${DOUBAO_LLM_PROVIDER_ID},${GEMINI_PROVIDER_ID}`,
  `standard LLM provider list should include Qwen, Doubao, and Gemini, got ${standardLlmIds.join(',')}`,
);
assert(
  !(standardLlmIds as readonly string[]).includes(OPENAI_COMPATIBLE_PROVIDER_ID),
  'standard LLM provider list must not expose OpenAI-compatible',
);
assert(
  normalizeVisibleLlmProvider(QWEN_LLM_PROVIDER_ID) === QWEN_LLM_PROVIDER_ID,
  'visible LLM provider normalization should preserve Qwen',
);
assert(
  normalizeVisibleLlmProvider(GEMINI_PROVIDER_ID) === GEMINI_PROVIDER_ID,
  'visible LLM provider normalization should preserve Gemini',
);
assert(
  normalizeVisibleLlmProvider(DOUBAO_LLM_PROVIDER_ID) === DOUBAO_LLM_PROVIDER_ID,
  'visible LLM provider normalization should preserve Doubao',
);
assert(
  normalizeVisibleLlmProvider(OPENAI_COMPATIBLE_PROVIDER_ID) === OPENAI_COMPATIBLE_PROVIDER_ID,
  'visible LLM provider normalization should preserve OpenAI-compatible',
);
assert(
  llmPresetSelectionForVisibleProvider(OPENAI_COMPATIBLE_PROVIDER_ID, `${QWEN_LLM_PROVIDER_ID}:qwen3.6-plus`) ===
    OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY,
  'active OpenAI-compatible should map to the explicit normal-select sentinel, not a Qwen preset',
);
assert(
  llmPresetSelectionForVisibleProvider(QWEN_LLM_PROVIDER_ID, `${QWEN_LLM_PROVIDER_ID}:qwen3.5-flash`) ===
    `${QWEN_LLM_PROVIDER_ID}:qwen3.5-flash`,
  'standard Qwen active provider should keep the matched Qwen preset selected',
);
assert(
  llmPresetSelectionForVisibleProvider(GEMINI_PROVIDER_ID, `${GEMINI_PROVIDER_ID}:gemini-2.5-flash`) ===
    `${GEMINI_PROVIDER_ID}:gemini-2.5-flash`,
  'standard Gemini active provider should keep the matched Gemini preset selected',
);
assert(
  llmPresetSelectionForVisibleProvider(DOUBAO_LLM_PROVIDER_ID, `${DOUBAO_LLM_PROVIDER_ID}:doubao-seed-2-0-lite-260215`) ===
    `${DOUBAO_LLM_PROVIDER_ID}:doubao-seed-2-0-lite-260215`,
  'standard Doubao active provider should keep the matched Doubao preset selected',
);
assert(
  llmPresetSelectionForVisibleProvider('unknown', `${QWEN_LLM_PROVIDER_ID}:qwen3.5-flash`) ===
    `${QWEN_LLM_PROVIDER_ID}:qwen3.5-flash`,
  'unknown active provider should use the standard fallback preset instead of the OpenAI-compatible sentinel',
);
assert(
  normalizeVisibleLlmProvider(null) === QWEN_LLM_PROVIDER_ID,
  'visible LLM provider normalization should default null to Qwen',
);
assert(
  normalizeVisibleLlmProvider('unknown') === QWEN_LLM_PROVIDER_ID,
  'visible LLM provider normalization should default unknown providers to Qwen',
);
assert(
  isAdvancedOpenAiCompatibleConfigVisible(OPENAI_COMPATIBLE_PROVIDER_ID, false),
  'advanced OpenAI-compatible config should show when it is already active',
);
assert(
  !isAdvancedOpenAiCompatibleConfigVisible(QWEN_LLM_PROVIDER_ID, false),
  'advanced OpenAI-compatible config should stay hidden unless expanded or already active',
);
assert(
  outputPrefsPatchForUiLanguageChange() === null,
  'UI language changes must not update dictation output language preferences',
);
assert(
  providerSwitchControlsDisabled(true),
  'credential controls should be disabled while provider switching is in flight',
);
assert(
  !providerSwitchControlsDisabled(false),
  'credential controls should stay enabled when provider switching is idle',
);

assert(
  settingsVisibleLocaleOptions().join(',') === 'zh-CN,en',
  `settings UI language select should only expose Simplified Chinese and English, got ${settingsVisibleLocaleOptions().join(',')}`,
);

assert(
  settingsVisibleOutputLanguageOptions().join(',') === 'zhCn,en',
  `settings output language select should only expose Simplified Chinese and English, got ${settingsVisibleOutputLanguageOptions().join(',')}`,
);

const legacyEnglishOutputPrefs = {
  chineseScriptPreference: 'auto',
  outputLanguagePreference: 'en',
  outputLanguagePreferenceExplicit: false,
} as const;
const normalizedLegacyOutput = normalizeLegacyOutputLanguagePrefs(
  legacyEnglishOutputPrefs,
  null,
);
assert(
  normalizedLegacyOutput.changed,
  'legacy output prefs without explicit marker should be written back normalized',
);
assert(
  normalizedLegacyOutput.prefs.outputLanguagePreference === 'auto',
  'legacy English output pref without explicit marker should normalize to auto',
);
assert(
  normalizedLegacyOutput.prefs.chineseScriptPreference === 'auto',
  'legacy output pref normalization should keep Chinese script auto',
);
assert(
  !normalizedLegacyOutput.prefs.outputLanguagePreferenceExplicit,
  'legacy output pref normalization should not mark output language explicit',
);

const explicitEnglishOutput = normalizeLegacyOutputLanguagePrefs(
  legacyEnglishOutputPrefs,
  'en',
);
assert(
  explicitEnglishOutput.changed,
  'stored explicit output language should be written back to backend explicit marker',
);
assert(
  explicitEnglishOutput.prefs.outputLanguagePreference === 'en',
  'explicit English output selection must still be preserved',
);
assert(
  explicitEnglishOutput.prefs.outputLanguagePreferenceExplicit,
  'explicit English output selection should mark backend prefs explicit',
);

for (const preset of ASR_PROVIDER_PRESETS) {
  assert(preset.apiKeyUrl.length > 0, `${preset.labelKey} should expose an API key URL`);
  assert('apiKeyLinkKey' in preset, `${preset.labelKey} should expose an API key link i18n key`);
  assert(
    typeof preset.apiKeyLinkKey === 'string' && preset.apiKeyLinkKey.length > 0,
    `${preset.labelKey} API key link i18n key should be non-empty`,
  );
}

for (const preset of LLM_MODEL_PRESETS) {
  assert(String(preset.providerId) !== OPENAI_COMPATIBLE_PROVIDER_ID, `${preset.labelKey} should not be OpenAI-compatible`);
  assert(preset.apiKeyUrl.length > 0, `${preset.labelKey} should expose an API key URL`);
  assert('apiKeyLinkKey' in preset, `${preset.labelKey} should expose an API key link i18n key`);
  assert(
    typeof preset.apiKeyLinkKey === 'string' && preset.apiKeyLinkKey.length > 0,
    `${preset.labelKey} API key link i18n key should be non-empty`,
  );
}
