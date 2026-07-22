import { GEMINI_PROVIDER_ID, OPENAI_COMPATIBLE_PROVIDER_ID, QWEN_LLM_PROVIDER_ID } from './product';

export type WhisperInputLlmProviderId =
  | typeof QWEN_LLM_PROVIDER_ID
  | typeof OPENAI_COMPATIBLE_PROVIDER_ID
  | typeof GEMINI_PROVIDER_ID;

export interface WhisperInputLlmProvider {
  id: WhisperInputLlmProviderId;
  label: string;
  defaultBaseUrl: string;
  defaultModel: string;
}

export const LLM_PROVIDERS: ReadonlyArray<WhisperInputLlmProvider> = [
  {
    id: QWEN_LLM_PROVIDER_ID,
    label: 'Qwen Flash · qwen3.5-flash',
    defaultBaseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    defaultModel: 'qwen3.5-flash',
  },
  {
    id: GEMINI_PROVIDER_ID,
    label: 'Gemini',
    defaultBaseUrl: 'https://generativelanguage.googleapis.com/v1beta',
    defaultModel: 'gemini-2.5-flash',
  },
  {
    id: OPENAI_COMPATIBLE_PROVIDER_ID,
    label: 'OpenAI-compatible',
    defaultBaseUrl: 'https://api.openai.com/v1',
    defaultModel: 'gpt-4o-mini',
  },
];
