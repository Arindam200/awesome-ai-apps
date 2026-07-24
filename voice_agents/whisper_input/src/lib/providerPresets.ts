import {
  DOUBAO_ASR_PROVIDER_ID,
  DOUBAO_LLM_PROVIDER_ID,
  GEMINI_PROVIDER_ID,
  OPENAI_COMPATIBLE_PROVIDER_ID,
  QWEN_LLM_PROVIDER_ID,
  QWEN_REALTIME_ASR_PROVIDER_ID,
} from './product';

export type CloudCredentialAccount =
  | 'asr.qwen.api_key'
  | 'asr.doubao.api_key'
  | 'llm.qwen.api_key'
  | 'llm.gemini.api_key'
  | 'ark.api_key';

export type AsrProviderPreset = {
  id: typeof QWEN_REALTIME_ASR_PROVIDER_ID | typeof DOUBAO_ASR_PROVIDER_ID;
  labelKey: string;
  model: string;
  apiKeyAccount: CloudCredentialAccount;
  apiKeyUrl: string;
  apiKeyLinkKey: string;
};

export type LlmModelPreset = {
  providerId: typeof QWEN_LLM_PROVIDER_ID | typeof DOUBAO_LLM_PROVIDER_ID | typeof GEMINI_PROVIDER_ID;
  model: string;
  labelKey: string;
  apiKeyAccount: CloudCredentialAccount;
  apiKeyUrl: string;
  apiKeyLinkKey: string;
};

export const PROVIDER_API_KEY_LABEL_KEYS = {
  qwen: 'settings.providers.getQwenApiKey',
  doubao: 'settings.providers.getDoubaoApiKey',
  gemini: 'settings.providers.getGeminiApiKey',
} as const;

export const PROVIDER_API_KEY_URLS = {
  qwen: 'https://modelstudio.console.alibabacloud.com/ap-southeast-1?tab=api#/api',
  doubaoAsr: 'https://console.volcengine.com/speech/app',
  doubaoLlm: 'https://console.volcengine.com/ark/apiKey',
  gemini: 'https://aistudio.google.com/apikey',
} as const;

export const ASR_PROVIDER_PRESETS = [
  {
    id: QWEN_REALTIME_ASR_PROVIDER_ID,
    labelKey: 'settings.providers.presets.asrQwenRealtime',
    model: 'qwen3-asr-flash-realtime',
    apiKeyAccount: 'asr.qwen.api_key',
    apiKeyUrl: PROVIDER_API_KEY_URLS.qwen,
    apiKeyLinkKey: PROVIDER_API_KEY_LABEL_KEYS.qwen,
  },
  {
    id: DOUBAO_ASR_PROVIDER_ID,
    labelKey: 'settings.providers.presets.asrDoubaoStreaming',
    model: 'doubao-streaming-asr-2',
    apiKeyAccount: 'asr.doubao.api_key',
    apiKeyUrl: PROVIDER_API_KEY_URLS.doubaoAsr,
    apiKeyLinkKey: PROVIDER_API_KEY_LABEL_KEYS.doubao,
  },
] as const satisfies ReadonlyArray<AsrProviderPreset>;

export const LLM_MODEL_PRESETS = [
  {
    providerId: QWEN_LLM_PROVIDER_ID,
    model: 'qwen3.5-flash',
    labelKey: 'settings.providers.presets.qwenFlash',
    apiKeyAccount: 'asr.qwen.api_key',
    apiKeyUrl: PROVIDER_API_KEY_URLS.qwen,
    apiKeyLinkKey: PROVIDER_API_KEY_LABEL_KEYS.qwen,
  },
  {
    providerId: DOUBAO_LLM_PROVIDER_ID,
    model: 'doubao-seed-2-0-lite-260215',
    labelKey: 'settings.providers.presets.doubaoSeed20Lite',
    apiKeyAccount: 'ark.api_key',
    apiKeyUrl: PROVIDER_API_KEY_URLS.doubaoLlm,
    apiKeyLinkKey: PROVIDER_API_KEY_LABEL_KEYS.doubao,
  },
  {
    providerId: GEMINI_PROVIDER_ID,
    model: 'gemini-2.5-flash',
    labelKey: 'settings.providers.presets.geminiFlash',
    apiKeyAccount: 'llm.gemini.api_key',
    apiKeyUrl: PROVIDER_API_KEY_URLS.gemini,
    apiKeyLinkKey: PROVIDER_API_KEY_LABEL_KEYS.gemini,
  },
  {
    providerId: GEMINI_PROVIDER_ID,
    model: 'gemini-3.1-flash-lite',
    labelKey: 'settings.providers.presets.gemini31FlashLite',
    apiKeyAccount: 'llm.gemini.api_key',
    apiKeyUrl: PROVIDER_API_KEY_URLS.gemini,
    apiKeyLinkKey: PROVIDER_API_KEY_LABEL_KEYS.gemini,
  },
] as const satisfies ReadonlyArray<LlmModelPreset>;

export const ADVANCED_LLM_PROVIDER_ID = OPENAI_COMPATIBLE_PROVIDER_ID;
