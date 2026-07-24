import { ASR_PROVIDER_PRESETS, LLM_MODEL_PRESETS } from './providerPresets';
import {
  DOUBAO_ASR_PROVIDER_ID,
  DOUBAO_LLM_PROVIDER_ID,
  GEMINI_PROVIDER_ID,
  QWEN_LLM_PROVIDER_ID,
  QWEN_REALTIME_ASR_PROVIDER_ID,
} from './product';
import { zhCN } from '../i18n/zh-CN';

function assertEqual(actual: string, expected: string, name: string) {
  if (actual !== expected) {
    throw new Error(`${name}: expected ${expected}, got ${actual}`);
  }
}

function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(message);
}

const qwenAsrPreset = ASR_PROVIDER_PRESETS.find(
  (preset) => preset.id === QWEN_REALTIME_ASR_PROVIDER_ID,
);
const doubaoAsrPreset = ASR_PROVIDER_PRESETS.find(
  (preset) => preset.id === DOUBAO_ASR_PROVIDER_ID,
);
const qwenLlmPreset = LLM_MODEL_PRESETS.find(
  (preset) => preset.providerId === QWEN_LLM_PROVIDER_ID,
);
const qwenFlashPreset = LLM_MODEL_PRESETS.find(
  (preset) => preset.providerId === QWEN_LLM_PROVIDER_ID && preset.model === 'qwen3.5-flash',
);
const qwenPlusPreset = LLM_MODEL_PRESETS.find(
  (preset) => preset.providerId === QWEN_LLM_PROVIDER_ID && String(preset.model) === 'qwen3.6-plus',
);
const doubaoLlmPreset = LLM_MODEL_PRESETS.find(
  (preset) => preset.providerId === DOUBAO_LLM_PROVIDER_ID,
);
const doubaoSeedLite = LLM_MODEL_PRESETS.find(
  (preset) => preset.providerId === DOUBAO_LLM_PROVIDER_ID && preset.model === 'doubao-seed-2-0-lite-260215',
);
const geminiLlmPreset = LLM_MODEL_PRESETS.find(
  (preset) => preset.providerId === GEMINI_PROVIDER_ID,
);
const geminiFlashLite = LLM_MODEL_PRESETS.find(
  p => p.providerId === GEMINI_PROVIDER_ID && p.model === 'gemini-3.1-flash-lite',
);
const qwenApiKeyUrl = 'https://modelstudio.console.alibabacloud.com/ap-southeast-1?tab=api#/api';
const doubaoAsrApiKeyUrl = 'https://console.volcengine.com/speech/app';
const doubaoLlmApiKeyUrl = 'https://console.volcengine.com/ark/apiKey';
const geminiApiKeyUrl = 'https://aistudio.google.com/apikey';

assert(Boolean(qwenAsrPreset), 'qwen ASR preset should exist');
assert(Boolean(doubaoAsrPreset), 'doubao ASR preset should exist');
assert(Boolean(qwenLlmPreset), 'qwen LLM preset should exist');
assert(
  qwenLlmPreset?.model === 'qwen3.5-flash',
  `default Qwen LLM preset should be qwen3.5-flash, got ${qwenLlmPreset?.model}`,
);
if (!qwenFlashPreset) throw new Error('Qwen Flash should use the fast low-cost model qwen3.5-flash');
assert(!qwenPlusPreset, 'Qwen Plus should not be exposed because it misses the 3s latency budget');
assert(Boolean(doubaoLlmPreset), 'doubao LLM preset should exist');
if (!doubaoSeedLite) throw new Error('Doubao Seed 2.0 Lite preset should remain available as a backup option');
assert(Boolean(geminiLlmPreset), 'gemini LLM preset should exist');
if (!geminiFlashLite) throw new Error('Gemini 3.1 Flash-Lite preset must exist');
assert(
  LLM_MODEL_PRESETS.some(p => p.providerId === DOUBAO_LLM_PROVIDER_ID),
  'Doubao LLM should remain exposed even when latency diagnostics do not recommend it as the fastest path',
);

assert(
  qwenAsrPreset?.apiKeyLinkKey === 'settings.providers.getQwenApiKey',
  `qwen ASR API key label should be service-specific, got ${qwenAsrPreset?.apiKeyLinkKey}`,
);

assert(
  doubaoAsrPreset?.apiKeyLinkKey === 'settings.providers.getDoubaoApiKey',
  `doubao ASR API key label should be service-specific, got ${doubaoAsrPreset?.apiKeyLinkKey}`,
);

assert(
  qwenLlmPreset?.apiKeyLinkKey === 'settings.providers.getQwenApiKey',
  `qwen LLM API key label should be service-specific, got ${qwenLlmPreset?.apiKeyLinkKey}`,
);

assert(
  doubaoLlmPreset?.apiKeyLinkKey === 'settings.providers.getDoubaoApiKey',
  `doubao LLM API key label should be service-specific, got ${doubaoLlmPreset?.apiKeyLinkKey}`,
);

assertEqual(
  qwenFlashPreset.labelKey,
  'settings.providers.presets.qwenFlash',
  'Qwen Flash label key',
);

assert(
  zhCN.settings.providers.presets.qwenFlash.includes('qwen3.5-flash'),
  `Qwen Flash label should show qwen3.5-flash, got ${zhCN.settings.providers.presets.qwenFlash}`,
);

assert(
  qwenLlmPreset?.apiKeyAccount === qwenAsrPreset?.apiKeyAccount,
  'qwen simple bundle should share one Bailian API key account across ASR and LLM',
);

assertEqual(qwenAsrPreset?.apiKeyUrl ?? '', qwenApiKeyUrl, 'Qwen ASR API Key direct URL');
assertEqual(qwenLlmPreset?.apiKeyUrl ?? '', qwenApiKeyUrl, 'Qwen LLM API Key direct URL');
assertEqual(doubaoAsrPreset?.apiKeyUrl ?? '', doubaoAsrApiKeyUrl, 'Doubao ASR API Key direct URL');
assertEqual(doubaoLlmPreset?.apiKeyUrl ?? '', doubaoLlmApiKeyUrl, 'Doubao LLM API Key direct URL');

assert(
  doubaoLlmPreset?.apiKeyAccount === 'ark.api_key',
  `doubao LLM should use Ark API key account, got ${doubaoLlmPreset?.apiKeyAccount}`,
);

assertEqual(
  doubaoSeedLite.labelKey,
  'settings.providers.presets.doubaoSeed20Lite',
  'Doubao Seed 2.0 Lite label key',
);

assert(
  geminiLlmPreset?.apiKeyLinkKey === 'settings.providers.getGeminiApiKey',
  `gemini LLM API key label should be service-specific, got ${geminiLlmPreset?.apiKeyLinkKey}`,
);

assertEqual(
  geminiFlashLite.apiKeyLinkKey,
  'settings.providers.getGeminiApiKey',
  'Gemini 3.1 Flash-Lite API Key 文案',
);

assertEqual(geminiFlashLite.apiKeyUrl, geminiApiKeyUrl, 'Gemini API Key direct URL');

assertEqual(
  geminiFlashLite.labelKey,
  'settings.providers.presets.gemini31FlashLite',
  'Gemini 3.1 Flash-Lite label key',
);

assert(
  qwenAsrPreset?.apiKeyUrl !== doubaoAsrPreset?.apiKeyUrl,
  'qwen ASR and doubao ASR should use distinct API key URLs',
);

assert(
  qwenLlmPreset?.apiKeyUrl !== geminiLlmPreset?.apiKeyUrl,
  'qwen LLM and gemini LLM should use distinct API key URLs',
);

assert(
  doubaoAsrPreset?.apiKeyUrl !== doubaoLlmPreset?.apiKeyUrl,
  'doubao ASR and doubao LLM should use their own service console URLs',
);
